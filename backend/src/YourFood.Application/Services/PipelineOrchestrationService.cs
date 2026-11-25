using System.Text;
using System.Text.Json;
using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Domain.Constants;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;
using YourFood.Domain.Repositories;

namespace YourFood.Application.Services;

public interface IPipelineOrchestrationService
{
    Task<ExportDatasetResponseDto> ExportDatasetAsync(Guid actorId, ExportDatasetRequest request, CancellationToken ct = default);
    Task<PipelineJobDto> ExecutePipelineStepAsync(Guid actorId, TriggerPipelineJobRequest request, CancellationToken ct = default);
    Task<IReadOnlyList<PipelineJobDto>> GetRecentJobsAsync(int limit = 25, CancellationToken ct = default);
    Task<PipelineJobDto> GetJobAsync(Guid jobId, CancellationToken ct = default);
    Task<PipelineAnalyticsDto> GetAnalyticsAsync(Guid? storeId = null, CancellationToken ct = default);
    Task<IReadOnlyList<AuditLogDto>> GetAuditLogsAsync(int limit = 50, CancellationToken ct = default);
}

public class PipelineOrchestrationService : IPipelineOrchestrationService
{
    private readonly IReviewRepository _reviews;
    private readonly IStoreRepository _stores;
    private readonly IOrderRepository _orders;
    private readonly IPipelineJobRepository _jobs;
    private readonly IAuditLogRepository _auditLogs;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IPipelineProcessRunner _runner;
    private readonly IAuditTrailService _audit;

    public PipelineOrchestrationService(
        IReviewRepository reviews,
        IStoreRepository stores,
        IOrderRepository orders,
        IPipelineJobRepository jobs,
        IAuditLogRepository auditLogs,
        IUnitOfWork unitOfWork,
        IPipelineProcessRunner runner,
        IAuditTrailService audit)
    {
        _reviews = reviews;
        _stores = stores;
        _orders = orders;
        _jobs = jobs;
        _auditLogs = auditLogs;
        _unitOfWork = unitOfWork;
        _runner = runner;
        _audit = audit;
    }

    public async Task<ExportDatasetResponseDto> ExportDatasetAsync(Guid actorId, ExportDatasetRequest request, CancellationToken ct = default)
    {
        var reviews = await _reviews.GetAllDetailedAsync(null, null, null, ct);
        var filtered = request.ExcludeFlagged ? reviews.Where(r => !r.RequiresReview).ToList() : reviews.ToList();

        var isCsv = string.Equals(request.Format, "csv", StringComparison.OrdinalIgnoreCase);
        var fileName = isCsv ? "delivery_reviews.csv" : "delivery_reviews.jsonl";
        var sb = new StringBuilder();
        var rowCount = 0;

        if (isCsv)
        {
            sb.AppendLine("review_id,text,aspect,sentiment,rating,user_id,store_id,order_id,created_at,evidence_text,start_offset,end_offset,requires_review");
        }

        foreach (var review in filtered)
        {
            if (review.Annotations.Count > 0)
            {
                foreach (var ann in review.Annotations)
                {
                    AppendDatasetRow(sb, isCsv, review, ann);
                    rowCount++;
                }
            }
            else if (request.IncludeUnannotated)
            {
                AppendDatasetRow(sb, isCsv, review, null);
                rowCount++;
            }

            review.MarkExported();
            _reviews.Update(review);
        }

        var content = sb.ToString();
        string? savedPath = null;
        if (request.SaveToPipelineRawDir)
        {
            savedPath = _runner.SaveDatasetFile(fileName, content);
        }

        await _audit.RecordAsync(actorId, "DATASET_EXPORTED", "Dataset", fileName, new { Reviews = filtered.Count, Rows = rowCount, request.Format }, $"Exported {rowCount} canonical rows to {fileName}", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return new ExportDatasetResponseDto(filtered.Count, rowCount, fileName, savedPath, content);
    }

    public async Task<PipelineJobDto> ExecutePipelineStepAsync(Guid actorId, TriggerPipelineJobRequest request, CancellationToken ct = default)
    {
        var datasetFile = string.IsNullOrWhiteSpace(request.DatasetFileName) ? "delivery_reviews.jsonl" : request.DatasetFileName;

        if (request.Step == PipelineStepType.ExportDataset)
        {
            var export = await ExportDatasetAsync(actorId, new ExportDatasetRequest("jsonl", true, true, true), ct);
            var exportJob = new PipelineJob(PipelineStepType.ExportDataset, actorId, $"export -> {export.SavedPath}");
            exportJob.MarkRunning();
            exportJob.MarkCompleted(0, $"Exported {export.TotalReviews} reviews ({export.TotalRows} rows) to {export.SavedPath}", string.Empty, JsonSerializer.Serialize(new { export.TotalReviews, export.TotalRows, export.SavedPath }));
            await _jobs.AddAsync(exportJob, ct);
            await _unitOfWork.SaveChangesAsync(ct);
            return MapJob(exportJob);
        }

        var preview = _runner.BuildCommandPreview(request.Step, datasetFile, request.Seed);
        var job = new PipelineJob(request.Step, actorId, preview);
        job.MarkRunning();
        await _jobs.AddAsync(job, ct);
        await _unitOfWork.SaveChangesAsync(ct);

        var (exitCode, outputLog, errorLog, reportJson) = await _runner.ExecuteStepAsync(request.Step, datasetFile, request.Seed, ct);
        job.MarkCompleted(exitCode, outputLog, errorLog, reportJson);
        _jobs.Update(job);

        await _audit.RecordAsync(actorId, "PIPELINE_STEP_EXECUTED", nameof(PipelineJob), job.Id.ToString(), new { request.Step, exitCode }, $"Pipeline step {request.Step} finished with exit code {exitCode}", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return MapJob(job);
    }

    public async Task<IReadOnlyList<PipelineJobDto>> GetRecentJobsAsync(int limit = 25, CancellationToken ct = default)
    {
        var jobs = await _jobs.GetRecentJobsAsync(Math.Clamp(limit, 1, 100), ct);
        return jobs.Select(MapJob).ToList();
    }

    public async Task<PipelineJobDto> GetJobAsync(Guid jobId, CancellationToken ct = default)
    {
        var job = await _jobs.GetByIdAsync(jobId, ct)
            ?? throw new NotFoundException(nameof(PipelineJob), jobId);
        return MapJob(job);
    }

    public async Task<PipelineAnalyticsDto> GetAnalyticsAsync(Guid? storeId = null, CancellationToken ct = default)
    {
        var stores = await _stores.GetAllAsync(ct);
        var orders = storeId.HasValue
            ? await _orders.GetByStoreIdAsync(storeId.Value, ct)
            : await _orders.GetAllAsync(ct);
        var reviews = await _reviews.GetAllDetailedAsync(storeId, null, null, ct);

        var aspectCounters = AbsaTaxonomy.Aspects.ToDictionary(
            a => a,
            a => (Pos: 0, Neg: 0, Neu: 0),
            StringComparer.OrdinalIgnoreCase);

        foreach (var review in reviews)
        {
            var items = review.Predictions.Count > 0
                ? review.Predictions.Select(p => (p.Aspect, p.Sentiment))
                : review.Annotations.Select(a => (a.Aspect, a.Sentiment));

            foreach (var (aspect, sentiment) in items)
            {
                if (!aspectCounters.TryGetValue(aspect, out var c)) continue;
                aspectCounters[aspect] = sentiment.ToLowerInvariant() switch
                {
                    "positivo" => (c.Pos + 1, c.Neg, c.Neu),
                    "negativo" => (c.Pos, c.Neg + 1, c.Neu),
                    _ => (c.Pos, c.Neg, c.Neu + 1)
                };
            }
        }

        var aspectBreakdown = AbsaTaxonomy.Aspects
            .Select(aspect =>
            {
                var c = aspectCounters[aspect];
                return new AspectSentimentCountDto(aspect, AbsaTaxonomy.ResolveEntity(aspect), c.Pos, c.Neg, c.Neu, c.Pos + c.Neg + c.Neu);
            })
            .ToList();

        var entityBreakdown = aspectBreakdown
            .GroupBy(a => a.Entity)
            .Select(g => new EntityBreakdownDto(
                g.Key,
                g.Sum(x => x.Positive),
                g.Sum(x => x.Negative),
                g.Sum(x => x.Neutral),
                g.Sum(x => x.Total)))
            .ToList();

        var avgRating = reviews.Count > 0 ? Math.Round(reviews.Average(r => r.Rating), 2) : 0.0;

        return new PipelineAnalyticsDto(
            stores.Count,
            orders.Count,
            orders.Count(o => o.Status == OrderStatus.Delivered),
            reviews.Count,
            reviews.Count(r => r.Annotations.Count > 0),
            reviews.Count(r => r.LastAnalyzedAtUtc.HasValue),
            reviews.Count(r => r.RequiresReview),
            avgRating,
            aspectBreakdown,
            entityBreakdown);
    }

    public async Task<IReadOnlyList<AuditLogDto>> GetAuditLogsAsync(int limit = 50, CancellationToken ct = default)
    {
        var logs = await _auditLogs.GetRecentAsync(Math.Clamp(limit, 1, 200), ct);
        return logs.Select(l => new AuditLogDto(l.Id, l.ActorUserId, l.Action, l.EntityType, l.EntityId, l.CorrelationId, l.PayloadHash, l.Summary, l.CreatedAtUtc)).ToList();
    }

    private static void AppendDatasetRow(StringBuilder sb, bool isCsv, Review review, ReviewAnnotation? annotation)
    {
        if (isCsv)
        {
            sb.AppendLine(string.Join(",",
                EscapeCsv(review.Id.ToString()),
                EscapeCsv(review.Text),
                EscapeCsv(annotation?.Aspect ?? string.Empty),
                EscapeCsv(annotation?.Sentiment ?? string.Empty),
                review.Rating.ToString(),
                EscapeCsv(review.CustomerId.ToString()),
                EscapeCsv(review.StoreId.ToString()),
                EscapeCsv(review.OrderId.ToString()),
                EscapeCsv(review.CreatedAtUtc.ToString("O")),
                EscapeCsv(annotation?.EvidenceText ?? string.Empty),
                annotation?.StartOffset?.ToString() ?? string.Empty,
                annotation?.EndOffset?.ToString() ?? string.Empty,
                review.RequiresReview ? "true" : "false"));
            return;
        }

        var obj = new Dictionary<string, object?>
        {
            ["review_id"] = review.Id.ToString(),
            ["text"] = review.Text,
            ["aspect"] = annotation?.Aspect,
            ["sentiment"] = annotation?.Sentiment,
            ["rating"] = review.Rating,
            ["user_id"] = review.CustomerId.ToString(),
            ["store_id"] = review.StoreId.ToString(),
            ["order_id"] = review.OrderId.ToString(),
            ["created_at"] = review.CreatedAtUtc.ToString("O"),
            ["evidence_text"] = annotation?.EvidenceText,
            ["start_offset"] = annotation?.StartOffset,
            ["end_offset"] = annotation?.EndOffset,
            ["requires_review"] = review.RequiresReview
        };

        sb.AppendLine(JsonSerializer.Serialize(obj));
    }

    private static string EscapeCsv(string value)
    {
        if (value.Contains(',') || value.Contains('"') || value.Contains('\n') || value.Contains('\r'))
            return $"\"{value.Replace("\"", "\"\"")}\"";
        return value;
    }

    private static PipelineJobDto MapJob(PipelineJob job) =>
        new(
            job.Id,
            job.Step.ToString(),
            job.Status.ToString(),
            job.TriggeredByUserId,
            job.CommandExecuted,
            job.OutputLog,
            job.ErrorLog,
            job.ExitCode,
            job.CreatedAtUtc,
            job.StartedAtUtc,
            job.CompletedAtUtc,
            job.ReportJson);
}
