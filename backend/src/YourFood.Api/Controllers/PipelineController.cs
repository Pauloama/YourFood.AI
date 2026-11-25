using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using YourFood.Api.Extensions;
using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Application.Services;
using YourFood.Domain.Constants;

namespace YourFood.Api.Controllers;

[ApiController]
[Route("api/v1/pipeline")]
[Authorize]
public class PipelineController : ControllerBase
{
    private readonly IPipelineOrchestrationService _pipelineService;
    private readonly IAbsaInferenceClient _absaClient;
    private readonly ICorrelationContext _correlation;

    public PipelineController(
        IPipelineOrchestrationService pipelineService,
        IAbsaInferenceClient absaClient,
        ICorrelationContext correlation)
    {
        _pipelineService = pipelineService;
        _absaClient = absaClient;
        _correlation = correlation;
    }

    [HttpGet("taxonomy")]
    [AllowAnonymous]
    public ActionResult GetTaxonomy() =>
        Ok(new
        {
            version = AbsaTaxonomy.Version,
            aspects = AbsaTaxonomy.Aspects,
            sentiments = AbsaTaxonomy.Sentiments,
            entityMapping = AbsaTaxonomy.EntityMapping
        });

    [HttpGet("health")]
    [AllowAnonymous]
    public async Task<ActionResult<AbsaHealthDto>> GetAbsaHealth(CancellationToken ct) =>
        Ok(await _absaClient.CheckHealthAsync(ct));

    [HttpGet("analytics")]
    public async Task<ActionResult<PipelineAnalyticsDto>> GetAnalytics([FromQuery] Guid? storeId, CancellationToken ct) =>
        Ok(await _pipelineService.GetAnalyticsAsync(storeId, ct));

    [HttpPost("export")]
    [Authorize(Roles = "Admin")]
    public async Task<ActionResult<ExportDatasetResponseDto>> ExportDataset([FromBody] ExportDatasetRequest request, CancellationToken ct) =>
        Ok(await _pipelineService.ExportDatasetAsync(User.GetUserId(), request, ct));

    [HttpPost("jobs")]
    [Authorize(Roles = "Admin")]
    public async Task<ActionResult<PipelineJobDto>> TriggerJob([FromBody] TriggerPipelineJobRequest request, CancellationToken ct) =>
        Ok(await _pipelineService.ExecutePipelineStepAsync(User.GetUserId(), request, ct));

    [HttpGet("jobs")]
    [Authorize(Roles = "Admin")]
    public async Task<ActionResult<IReadOnlyList<PipelineJobDto>>> GetJobs([FromQuery] int limit = 25, CancellationToken ct = default) =>
        Ok(await _pipelineService.GetRecentJobsAsync(limit, ct));

    [HttpGet("jobs/{jobId:guid}")]
    [Authorize(Roles = "Admin")]
    public async Task<ActionResult<PipelineJobDto>> GetJob(Guid jobId, CancellationToken ct) =>
        Ok(await _pipelineService.GetJobAsync(jobId, ct));

    [HttpPost("inference/analyze")]
    public async Task<ActionResult<AbsaAnalysisResponseDto>> AnalyzeText([FromBody] SingleInferenceRequest request, CancellationToken ct) =>
        Ok(await _absaClient.AnalyzeAsync(request.ReviewId ?? Guid.NewGuid().ToString("N"), request.Text, _correlation.CorrelationId, ct));

    [HttpPost("inference/classify-sentiment")]
    public async Task<ActionResult<DiagnosticSentimentResponseDto>> ClassifySentiment([FromBody] DiagnosticSentimentRequest request, CancellationToken ct) =>
        Ok(await _absaClient.ClassifySentimentAsync(request.Text, request.Aspect, _correlation.CorrelationId, ct));

    [HttpGet("audit-logs")]
    [Authorize(Roles = "Admin")]
    public async Task<ActionResult<IReadOnlyList<AuditLogDto>>> GetAuditLogs([FromQuery] int limit = 50, CancellationToken ct = default) =>
        Ok(await _pipelineService.GetAuditLogsAsync(limit, ct));
}
