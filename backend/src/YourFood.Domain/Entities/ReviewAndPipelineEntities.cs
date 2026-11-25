using YourFood.Domain.Constants;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;

namespace YourFood.Domain.Entities;

public class Review : BaseEntity
{
    public Guid OrderId { get; private set; }
    public Guid CustomerId { get; private set; }
    public Guid StoreId { get; private set; }
    public string Text { get; private set; } = string.Empty;
    public int Rating { get; private set; }
    public bool RequiresReview { get; private set; }
    public bool IsExportedToDataset { get; private set; }
    public DateTime? LastAnalyzedAtUtc { get; private set; }
    public string? AspectModelVersion { get; private set; }
    public string? SentimentModelVersion { get; private set; }
    public string? TaxonomyVersion { get; private set; }
    public double? LastInferenceLatencyMs { get; private set; }

    public Order Order { get; private set; } = null!;
    public User Customer { get; private set; } = null!;
    public Store Store { get; private set; } = null!;
    public ICollection<ReviewAnnotation> Annotations { get; private set; } = new List<ReviewAnnotation>();
    public ICollection<ReviewPrediction> Predictions { get; private set; } = new List<ReviewPrediction>();

    private Review() { }

    public Review(Guid orderId, Guid customerId, Guid storeId, string text, int rating)
    {
        if (string.IsNullOrWhiteSpace(text))
            throw new DomainException("Review text cannot be empty.", "EMPTY_REVIEW_TEXT");
        if (rating is < 1 or > 5)
            throw new DomainException("Rating must be between 1 and 5.", "INVALID_RATING");

        OrderId = orderId;
        CustomerId = customerId;
        StoreId = storeId;
        Text = text.Trim();
        Rating = rating;
    }

    public void SetAnnotations(IEnumerable<ReviewAnnotation> annotations)
    {
        Annotations.Clear();
        var sentimentsByAspect = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);

        foreach (var annotation in annotations)
        {
            annotation.AttachToReview(Id);
            Annotations.Add(annotation);

            if (!sentimentsByAspect.TryGetValue(annotation.Aspect, out var set))
            {
                set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                sentimentsByAspect[annotation.Aspect] = set;
            }

            set.Add(annotation.Sentiment);
        }

        RequiresReview = sentimentsByAspect.Values.Any(v => v.Count > 1);
        Touch();
    }

    public void FlagForReview(bool requiresReview)
    {
        RequiresReview = requiresReview;
        Touch();
    }

    public void MarkExported()
    {
        IsExportedToDataset = true;
        Touch();
    }

    public void RecordInference(
        IEnumerable<ReviewPrediction> predictions,
        string aspectModelVersion,
        string sentimentModelVersion,
        string taxonomyVersion,
        double latencyMs)
    {
        Predictions.Clear();
        foreach (var prediction in predictions)
        {
            prediction.AttachToReview(Id);
            Predictions.Add(prediction);
        }

        AspectModelVersion = aspectModelVersion;
        SentimentModelVersion = sentimentModelVersion;
        TaxonomyVersion = taxonomyVersion;
        LastInferenceLatencyMs = latencyMs;
        LastAnalyzedAtUtc = DateTime.UtcNow;
        Touch();
    }
}

public class ReviewAnnotation : BaseEntity
{
    public Guid ReviewId { get; private set; }
    public string Aspect { get; private set; } = string.Empty;
    public string Entity { get; private set; } = string.Empty;
    public string Sentiment { get; private set; } = string.Empty;
    public string? EvidenceText { get; private set; }
    public int? StartOffset { get; private set; }
    public int? EndOffset { get; private set; }

    public Review Review { get; private set; } = null!;

    private ReviewAnnotation() { }

    public ReviewAnnotation(string aspect, string sentiment, string? evidenceText = null, int? startOffset = null, int? endOffset = null)
    {
        if (!AbsaTaxonomy.IsValidAspect(aspect))
            throw new DomainException($"Aspect '{aspect}' is outside the official taxonomy.", "INVALID_ASPECT", 422);
        if (!AbsaTaxonomy.IsValidSentiment(sentiment))
            throw new DomainException($"Sentiment '{sentiment}' is invalid.", "INVALID_SENTIMENT", 422);
        if (startOffset.HasValue && endOffset.HasValue && (startOffset < 0 || startOffset >= endOffset))
            throw new DomainException("Invalid evidence offsets.", "INVALID_OFFSETS", 422);

        Aspect = aspect.Trim().ToLowerInvariant();
        Entity = AbsaTaxonomy.ResolveEntity(Aspect);
        Sentiment = sentiment.Trim().ToLowerInvariant();
        EvidenceText = string.IsNullOrWhiteSpace(evidenceText) ? null : evidenceText.Trim();
        StartOffset = startOffset;
        EndOffset = endOffset;
    }

    internal void AttachToReview(Guid reviewId)
    {
        ReviewId = reviewId;
    }
}

public class ReviewPrediction : BaseEntity
{
    public Guid ReviewId { get; private set; }
    public string Entity { get; private set; } = string.Empty;
    public string Aspect { get; private set; } = string.Empty;
    public double AspectProbability { get; private set; }
    public string Sentiment { get; private set; } = string.Empty;
    public double SentimentProbability { get; private set; }

    public Review Review { get; private set; } = null!;

    private ReviewPrediction() { }

    public ReviewPrediction(string entity, string aspect, double aspectProbability, string sentiment, double sentimentProbability)
    {
        Entity = entity;
        Aspect = aspect;
        AspectProbability = aspectProbability;
        Sentiment = sentiment;
        SentimentProbability = sentimentProbability;
    }

    internal void AttachToReview(Guid reviewId)
    {
        ReviewId = reviewId;
    }
}

public class PipelineJob : BaseEntity
{
    public PipelineStepType Step { get; private set; }
    public PipelineJobStatus Status { get; private set; }
    public Guid TriggeredByUserId { get; private set; }
    public string CommandExecuted { get; private set; } = string.Empty;
    public string OutputLog { get; private set; } = string.Empty;
    public string ErrorLog { get; private set; } = string.Empty;
    public int? ExitCode { get; private set; }
    public DateTime? StartedAtUtc { get; private set; }
    public DateTime? CompletedAtUtc { get; private set; }
    public string? ReportJson { get; private set; }

    private PipelineJob() { }

    public PipelineJob(PipelineStepType step, Guid triggeredByUserId, string commandExecuted)
    {
        Step = step;
        Status = PipelineJobStatus.Queued;
        TriggeredByUserId = triggeredByUserId;
        CommandExecuted = commandExecuted;
    }

    public void MarkRunning()
    {
        Status = PipelineJobStatus.Running;
        StartedAtUtc = DateTime.UtcNow;
        Touch();
    }

    public void MarkCompleted(int exitCode, string outputLog, string errorLog, string? reportJson = null)
    {
        ExitCode = exitCode;
        OutputLog = outputLog;
        ErrorLog = errorLog;
        ReportJson = reportJson;
        Status = exitCode == 0 ? PipelineJobStatus.Succeeded : PipelineJobStatus.Failed;
        CompletedAtUtc = DateTime.UtcNow;
        Touch();
    }
}

public class AuditLog : BaseEntity
{
    public Guid? ActorUserId { get; private set; }
    public string Action { get; private set; } = string.Empty;
    public string EntityType { get; private set; } = string.Empty;
    public string EntityId { get; private set; } = string.Empty;
    public string CorrelationId { get; private set; } = string.Empty;
    public string PayloadHash { get; private set; } = string.Empty;
    public string Summary { get; private set; } = string.Empty;

    private AuditLog() { }

    public AuditLog(Guid? actorUserId, string action, string entityType, string entityId, string correlationId, string payloadHash, string summary)
    {
        ActorUserId = actorUserId;
        Action = action;
        EntityType = entityType;
        EntityId = entityId;
        CorrelationId = correlationId;
        PayloadHash = payloadHash;
        Summary = summary;
    }
}

public class IdempotencyRecord : BaseEntity
{
    public string Key { get; private set; } = string.Empty;
    public string RequestPath { get; private set; } = string.Empty;
    public string RequestHash { get; private set; } = string.Empty;
    public int ResponseStatusCode { get; private set; }
    public string ResponseBody { get; private set; } = string.Empty;
    public DateTime ExpiresAtUtc { get; private set; }

    private IdempotencyRecord() { }

    public IdempotencyRecord(string key, string requestPath, string requestHash, int responseStatusCode, string responseBody, TimeSpan ttl)
    {
        Key = key;
        RequestPath = requestPath;
        RequestHash = requestHash;
        ResponseStatusCode = responseStatusCode;
        ResponseBody = responseBody;
        ExpiresAtUtc = DateTime.UtcNow.Add(ttl);
    }
}
