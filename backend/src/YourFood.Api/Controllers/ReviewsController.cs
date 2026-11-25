using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using YourFood.Api.Extensions;
using YourFood.Application.DTOs;
using YourFood.Application.Services;

namespace YourFood.Api.Controllers;

[ApiController]
[Route("api/v1/reviews")]
[Authorize]
public class ReviewsController : ControllerBase
{
    private readonly IReviewService _reviewService;

    public ReviewsController(IReviewService reviewService)
    {
        _reviewService = reviewService;
    }

    [HttpPost]
    [Authorize(Roles = "Customer,Admin")]
    public async Task<ActionResult<ReviewDto>> Create([FromBody] CreateReviewRequest request, CancellationToken ct)
    {
        var created = await _reviewService.CreateReviewAsync(User.GetUserId(), request, ct);
        return CreatedAtAction(nameof(GetById), new { reviewId = created.Id }, created);
    }

    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<ReviewDto>>> List(
        [FromQuery] Guid? storeId,
        [FromQuery] bool? onlyPendingInference,
        [FromQuery] bool? onlyFlagged,
        CancellationToken ct) =>
        Ok(await _reviewService.ListReviewsAsync(storeId, onlyPendingInference, onlyFlagged, ct));

    [HttpGet("{reviewId:guid}")]
    public async Task<ActionResult<ReviewDto>> GetById(Guid reviewId, CancellationToken ct) =>
        Ok(await _reviewService.GetReviewAsync(reviewId, ct));

    [HttpPut("{reviewId:guid}/annotations")]
    [Authorize(Roles = "Admin,StoreOwner")]
    public async Task<ActionResult<ReviewDto>> UpdateAnnotations(Guid reviewId, [FromBody] UpdateReviewAnnotationsRequest request, CancellationToken ct) =>
        Ok(await _reviewService.UpdateAnnotationsAsync(User.GetUserId(), reviewId, request, ct));

    [HttpPost("{reviewId:guid}/analyze")]
    [Authorize(Roles = "Admin,StoreOwner")]
    public async Task<ActionResult<ReviewDto>> AnalyzeReview(Guid reviewId, CancellationToken ct) =>
        Ok(await _reviewService.RunInferenceOnReviewAsync(User.GetUserId(), reviewId, ct));

    [HttpPost("analyze-batch")]
    [Authorize(Roles = "Admin")]
    public async Task<ActionResult<BatchInferenceSummaryDto>> AnalyzeBatch([FromBody] BatchInferenceRequest request, CancellationToken ct) =>
        Ok(await _reviewService.RunBatchInferenceAsync(User.GetUserId(), request, ct));
}
