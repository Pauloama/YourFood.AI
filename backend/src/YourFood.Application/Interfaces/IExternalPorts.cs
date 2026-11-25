using YourFood.Application.DTOs;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;

namespace YourFood.Application.Interfaces;

public interface IPasswordHasher
{
    string Hash(string password);
    bool Verify(string password, string hash);
}

public interface IJwtTokenService
{
    (string AccessToken, int ExpiresInSeconds) GenerateAccessToken(User user);
    (string RawRefreshToken, string TokenHash, DateTime ExpiresAtUtc) GenerateRefreshToken();
    string ComputeHash(string value);
}

public interface IAuditTrailService
{
    Task RecordAsync(Guid? actorUserId, string action, string entityType, string entityId, object payload, string summary, CancellationToken ct = default);
}

public interface IAbsaInferenceClient
{
    Task<AbsaHealthDto> CheckHealthAsync(CancellationToken ct = default);
    Task<AbsaAnalysisResponseDto> AnalyzeAsync(string reviewId, string text, string? correlationId = null, CancellationToken ct = default);
    Task<DiagnosticSentimentResponseDto> ClassifySentimentAsync(string text, string aspect, string? correlationId = null, CancellationToken ct = default);
}

public interface IPipelineProcessRunner
{
    string BuildCommandPreview(PipelineStepType step, string? datasetFileName, int seed);
    string SaveDatasetFile(string fileName, string content);
    Task<(int ExitCode, string OutputLog, string ErrorLog, string? ReportJson)> ExecuteStepAsync(PipelineStepType step, string? datasetFileName, int seed, CancellationToken ct = default);
}

public interface ICorrelationContext
{
    string CorrelationId { get; }
}
