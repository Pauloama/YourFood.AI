using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;
using YourFood.Domain.Repositories;

namespace YourFood.Application.Services;

public interface IReviewService
{
    Task<ReviewDto> CreateReviewAsync(Guid customerId, CreateReviewRequest request, CancellationToken ct = default);
    Task<ReviewDto> UpdateAnnotationsAsync(Guid actorId, Guid reviewId, UpdateReviewAnnotationsRequest request, CancellationToken ct = default);
    Task<IReadOnlyList<ReviewDto>> ListReviewsAsync(Guid? storeId, bool? onlyPendingInference, bool? onlyFlagged, CancellationToken ct = default);
    Task<ReviewDto> GetReviewAsync(Guid reviewId, CancellationToken ct = default);
    Task<ReviewDto> RunInferenceOnReviewAsync(Guid actorId, Guid reviewId, CancellationToken ct = default);
    Task<BatchInferenceSummaryDto> RunBatchInferenceAsync(Guid actorId, BatchInferenceRequest request, CancellationToken ct = default);
}

public class ReviewService : IReviewService
{
    private readonly IReviewRepository _reviews;
    private readonly IOrderRepository _orders;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IAbsaInferenceClient _absaClient;
    private readonly IAuditTrailService _audit;
    private readonly ICorrelationContext _correlation;

    public ReviewService(
        IReviewRepository reviews,
        IOrderRepository orders,
        IUnitOfWork unitOfWork,
        IAbsaInferenceClient absaClient,
        IAuditTrailService audit,
        ICorrelationContext correlation)
    {
        _reviews = reviews;
        _orders = orders;
        _unitOfWork = unitOfWork;
        _absaClient = absaClient;
        _audit = audit;
        _correlation = correlation;
    }

    public async Task<ReviewDto> CreateReviewAsync(Guid customerId, CreateReviewRequest request, CancellationToken ct = default)
    {
        var order = await _orders.GetByIdDetailedAsync(request.OrderId, ct)
            ?? throw new NotFoundException(nameof(Order), request.OrderId);

        if (order.CustomerId != customerId)
            throw new ForbiddenException("Only the customer who placed the order can submit a review.");

        if (order.Status != OrderStatus.Delivered)
            throw new DomainException("Reviews can only be submitted for delivered orders.", "ORDER_NOT_DELIVERED");

        var existing = await _reviews.GetByOrderIdAsync(order.Id, ct);
        if (existing is not null)
            throw new ConflictException("A review has already been submitted for this order.");

        var review = new Review(order.Id, customerId, order.StoreId, request.Text, request.Rating);

        if (request.Annotations is { Count: > 0 })
        {
            var domainAnnotations = request.Annotations
                .Select(a => new ReviewAnnotation(a.Aspect, a.Sentiment, a.EvidenceText, a.StartOffset, a.EndOffset))
                .ToList();
            review.SetAnnotations(domainAnnotations);
        }

        if (request.RunInferenceImmediately)
        {
            await TryApplyInferenceAsync(review, ct);
        }

        await _reviews.AddAsync(review, ct);
        await _audit.RecordAsync(customerId, "REVIEW_CREATED", nameof(Review), review.Id.ToString(), new { review.OrderId, review.Rating, review.RequiresReview }, "Customer submitted delivery review", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        var loaded = await _reviews.GetByIdDetailedAsync(review.Id, ct) ?? review;
        return MapReview(loaded, order.Store?.Name ?? string.Empty);
    }

    public async Task<ReviewDto> UpdateAnnotationsAsync(Guid actorId, Guid reviewId, UpdateReviewAnnotationsRequest request, CancellationToken ct = default)
    {
        var review = await _reviews.GetByIdDetailedAsync(reviewId, ct)
            ?? throw new NotFoundException(nameof(Review), reviewId);

        var annotations = request.Annotations
            .Select(a => new ReviewAnnotation(a.Aspect, a.Sentiment, a.EvidenceText, a.StartOffset, a.EndOffset))
            .ToList();

        review.SetAnnotations(annotations);
        if (request.RequiresReview.HasValue)
            review.FlagForReview(request.RequiresReview.Value);

        _reviews.Update(review);
        await _audit.RecordAsync(actorId, "REVIEW_ANNOTATED", nameof(Review), review.Id.ToString(), new { Count = annotations.Count, review.RequiresReview }, "Ground-truth ABSA annotations updated", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return MapReview(review, review.Store?.Name ?? string.Empty);
    }

    public async Task<IReadOnlyList<ReviewDto>> ListReviewsAsync(Guid? storeId, bool? onlyPendingInference, bool? onlyFlagged, CancellationToken ct = default)
    {
        var reviews = await _reviews.GetAllDetailedAsync(storeId, onlyPendingInference, onlyFlagged, ct);
        return reviews.Select(r => MapReview(r, r.Store?.Name ?? string.Empty)).ToList();
    }

    public async Task<ReviewDto> GetReviewAsync(Guid reviewId, CancellationToken ct = default)
    {
        var review = await _reviews.GetByIdDetailedAsync(reviewId, ct)
            ?? throw new NotFoundException(nameof(Review), reviewId);
        return MapReview(review, review.Store?.Name ?? string.Empty);
    }

    public async Task<ReviewDto> RunInferenceOnReviewAsync(Guid actorId, Guid reviewId, CancellationToken ct = default)
    {
        var review = await _reviews.GetByIdDetailedAsync(reviewId, ct)
            ?? throw new NotFoundException(nameof(Review), reviewId);

        var analysis = await _absaClient.AnalyzeAsync(review.Id.ToString(), review.Text, _correlation.CorrelationId, ct);
        ApplyAnalysisResult(review, analysis);

        _reviews.Update(review);
        await _audit.RecordAsync(actorId, "REVIEW_INFERENCE_RUN", nameof(Review), review.Id.ToString(), new { AspectsDetected = analysis.Aspects.Count, analysis.ProcessingTimeMs }, "ABSA inference executed on review", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return MapReview(review, review.Store?.Name ?? string.Empty);
    }

    public async Task<BatchInferenceSummaryDto> RunBatchInferenceAsync(Guid actorId, BatchInferenceRequest request, CancellationToken ct = default)
    {
        IReadOnlyList<Review> targets;
        if (request.ReviewIds is { Count: > 0 })
        {
            var all = await _reviews.GetAllDetailedAsync(null, null, null, ct);
            var idSet = request.ReviewIds.ToHashSet();
            targets = all.Where(r => idSet.Contains(r.Id)).Take(Math.Clamp(request.MaxCount, 1, 100)).ToList();
        }
        else
        {
            var pending = await _reviews.GetAllDetailedAsync(null, true, null, ct);
            targets = pending.Take(Math.Clamp(request.MaxCount, 1, 100)).ToList();
        }

        var processed = new List<ReviewDto>();
        var failed = 0;
        var totalLatency = 0.0;

        foreach (var review in targets)
        {
            try
            {
                var analysis = await _absaClient.AnalyzeAsync(review.Id.ToString(), review.Text, _correlation.CorrelationId, ct);
                ApplyAnalysisResult(review, analysis);
                _reviews.Update(review);
                totalLatency += analysis.ProcessingTimeMs;
                processed.Add(MapReview(review, review.Store?.Name ?? string.Empty));
            }
            catch
            {
                failed++;
            }
        }

        await _audit.RecordAsync(actorId, "BATCH_INFERENCE_RUN", nameof(Review), "batch", new { Processed = processed.Count, Failed = failed }, "Batch ABSA inference executed", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return new BatchInferenceSummaryDto(processed.Count, failed, Math.Round(totalLatency, 2), processed);
    }

    private async Task TryApplyInferenceAsync(Review review, CancellationToken ct)
    {
        try
        {
            var analysis = await _absaClient.AnalyzeAsync(review.Id.ToString(), review.Text, _correlation.CorrelationId, ct);
            ApplyAnalysisResult(review, analysis);
        }
        catch
        {
        }
    }

    private static void ApplyAnalysisResult(Review review, AbsaAnalysisResponseDto analysis)
    {
        var predictions = analysis.Aspects
            .Select(a => new ReviewPrediction(a.Entity, a.Aspect, a.AspectProbability, a.Sentiment, a.SentimentProbability))
            .ToList();

        analysis.ModelVersions.TryGetValue("aspectDetector", out var aspectVersion);
        analysis.ModelVersions.TryGetValue("sentimentClassifier", out var sentimentVersion);
        analysis.ModelVersions.TryGetValue("taxonomy", out var taxonomyVersion);

        review.RecordInference(
            predictions,
            aspectVersion ?? "unknown",
            sentimentVersion ?? "unknown",
            taxonomyVersion ?? "food-reviews-taxonomy-v1",
            analysis.ProcessingTimeMs);
    }

    public static ReviewDto MapReview(Review review, string storeName) =>
        new(
            review.Id,
            review.OrderId,
            review.CustomerId,
            review.StoreId,
            storeName,
            review.Text,
            review.Rating,
            review.RequiresReview,
            review.IsExportedToDataset,
            review.CreatedAtUtc,
            review.LastAnalyzedAtUtc,
            review.AspectModelVersion,
            review.SentimentModelVersion,
            review.TaxonomyVersion,
            review.LastInferenceLatencyMs,
            review.Annotations.Select(a => new ReviewAnnotationDto(a.Id, a.Aspect, a.Entity, a.Sentiment, a.EvidenceText, a.StartOffset, a.EndOffset)).ToList(),
            review.Predictions.Select(p => new ReviewPredictionDto(p.Entity, p.Aspect, p.AspectProbability, p.Sentiment, p.SentimentProbability)).ToList());
}
