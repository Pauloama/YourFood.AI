using YourFood.Domain.Enums;

namespace YourFood.Application.DTOs;

public record RegisterRequest(string FullName, string Email, string Password, UserRole Role);

public record LoginRequest(string Email, string Password);

public record RefreshTokenRequest(string RefreshToken);

public record OAuthAuthorizeRequest(string ClientId, string RedirectUri, string Scope, string? CodeChallenge);

public record OAuthTokenRequest(string GrantType, string? Code, string? RedirectUri, string? ClientId, string? CodeVerifier, string? RefreshToken);

public record OAuthExternalLoginRequest(string Provider, string ExternalSubject, string Email, string FullName, UserRole? PreferredRole);

public record UserSummaryDto(Guid Id, string FullName, string Email, string Role, string? OAuthProvider);

public record AuthTokenResponse(string AccessToken, string RefreshToken, string TokenType, int ExpiresInSeconds, UserSummaryDto User);

public record OAuthAuthorizeResponse(string Code, string RedirectUri, string Scope, DateTime ExpiresAtUtc);

public record CreateStoreRequest(string Name, string Category, string Description, string Address, decimal DeliveryFee, int EstimatedDeliveryMinutes);

public record UpdateStoreRequest(string Name, string Category, string Description, string Address, decimal DeliveryFee, int EstimatedDeliveryMinutes, bool IsOpen);

public record CreateMenuItemRequest(string Name, string Description, string Category, decimal Price);

public record UpdateMenuItemRequest(string Name, string Description, string Category, decimal Price, bool IsAvailable);

public record MenuItemDto(Guid Id, Guid StoreId, string Name, string Description, string Category, decimal Price, string CurrencyCode, bool IsAvailable);

public record StoreDto(Guid Id, Guid OwnerId, string Name, string Category, string Description, string Address, decimal DeliveryFee, int EstimatedDeliveryMinutes, bool IsOpen, IReadOnlyList<MenuItemDto> MenuItems);

public record OrderItemInput(Guid MenuItemId, int Quantity);

public record CreateOrderRequest(Guid StoreId, string DeliveryAddress, string? Notes, IReadOnlyList<OrderItemInput> Items);

public record TransitionOrderStatusRequest(OrderStatus NextStatus, string? Reason);

public record OrderItemDto(Guid Id, Guid MenuItemId, string ItemNameSnapshot, decimal UnitPriceSnapshot, int Quantity, decimal LineTotal);

public record OrderStateTransitionDto(Guid Id, string? FromStatus, string ToStatus, Guid ActorUserId, string? Reason, DateTime CreatedAtUtc);

public record LedgerEntryDto(Guid Id, string EntryType, decimal Amount, string CurrencyCode, string Description, DateTime CreatedAtUtc);

public record OrderDto(
    Guid Id,
    Guid CustomerId,
    Guid StoreId,
    string StoreName,
    string DeliveryAddress,
    string Status,
    IReadOnlyList<string> AllowedNextStatuses,
    decimal SubtotalAmount,
    decimal DeliveryFeeAmount,
    decimal TotalAmount,
    string CurrencyCode,
    string? Notes,
    bool HasReview,
    DateTime CreatedAtUtc,
    IReadOnlyList<OrderItemDto> Items,
    IReadOnlyList<OrderStateTransitionDto> StateHistory,
    IReadOnlyList<LedgerEntryDto> LedgerEntries);

public record ReviewAnnotationInput(string Aspect, string Sentiment, string? EvidenceText, int? StartOffset, int? EndOffset);

public record CreateReviewRequest(Guid OrderId, string Text, int Rating, bool RunInferenceImmediately, IReadOnlyList<ReviewAnnotationInput>? Annotations);

public record UpdateReviewAnnotationsRequest(IReadOnlyList<ReviewAnnotationInput> Annotations, bool? RequiresReview);

public record ReviewAnnotationDto(Guid Id, string Aspect, string Entity, string Sentiment, string? EvidenceText, int? StartOffset, int? EndOffset);

public record ReviewPredictionDto(string Entity, string Aspect, double AspectProbability, string Sentiment, double SentimentProbability);

public record ReviewDto(
    Guid Id,
    Guid OrderId,
    Guid CustomerId,
    Guid StoreId,
    string StoreName,
    string Text,
    int Rating,
    bool RequiresReview,
    bool IsExportedToDataset,
    DateTime CreatedAtUtc,
    DateTime? LastAnalyzedAtUtc,
    string? AspectModelVersion,
    string? SentimentModelVersion,
    string? TaxonomyVersion,
    double? LastInferenceLatencyMs,
    IReadOnlyList<ReviewAnnotationDto> Annotations,
    IReadOnlyList<ReviewPredictionDto> Predictions);

public record AbsaHealthDto(string Status, bool AspectModelLoaded, bool SentimentModelLoaded, string ServiceUrl);

public record SingleInferenceRequest(string? ReviewId, string Text);

public record AbsaAnalysisResponseDto(
    string ReviewId,
    string Text,
    IReadOnlyList<ReviewPredictionDto> Aspects,
    IReadOnlyDictionary<string, string> ModelVersions,
    double ProcessingTimeMs);

public record BatchInferenceRequest(IReadOnlyList<Guid>? ReviewIds, int MaxCount = 32);

public record BatchInferenceSummaryDto(int ProcessedCount, int FailedCount, double TotalLatencyMs, IReadOnlyList<ReviewDto> Results);

public record DiagnosticSentimentRequest(string Text, string Aspect);

public record DiagnosticSentimentResponseDto(
    string Text,
    string Aspect,
    string Entity,
    string PredictedSentiment,
    double Probability,
    IReadOnlyDictionary<string, double> Probabilities);

public record ExportDatasetRequest(string Format = "jsonl", bool IncludeUnannotated = true, bool ExcludeFlagged = true, bool SaveToPipelineRawDir = true);

public record ExportDatasetResponseDto(int TotalReviews, int TotalRows, string FileName, string? SavedPath, string Content);

public record TriggerPipelineJobRequest(PipelineStepType Step, string? DatasetFileName = null, int Seed = 42);

public record PipelineJobDto(
    Guid Id,
    string Step,
    string Status,
    Guid TriggeredByUserId,
    string CommandExecuted,
    string OutputLog,
    string ErrorLog,
    int? ExitCode,
    DateTime CreatedAtUtc,
    DateTime? StartedAtUtc,
    DateTime? CompletedAtUtc,
    string? ReportJson);

public record AspectSentimentCountDto(string Aspect, string Entity, int Positive, int Negative, int Neutral, int Total);

public record EntityBreakdownDto(string Entity, int Positive, int Negative, int Neutral, int Total);

public record PipelineAnalyticsDto(
    int TotalStores,
    int TotalOrders,
    int DeliveredOrders,
    int TotalReviews,
    int AnnotatedReviews,
    int AnalyzedReviews,
    int FlaggedReviews,
    double AverageRating,
    IReadOnlyList<AspectSentimentCountDto> AspectBreakdown,
    IReadOnlyList<EntityBreakdownDto> EntityBreakdown);

public record AuditLogDto(Guid Id, Guid? ActorUserId, string Action, string EntityType, string EntityId, string CorrelationId, string PayloadHash, string Summary, DateTime CreatedAtUtc);
