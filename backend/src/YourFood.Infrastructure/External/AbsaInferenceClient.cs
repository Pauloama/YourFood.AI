using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Options;
using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Domain.Exceptions;

namespace YourFood.Infrastructure.External;

public class AbsaServiceSettings
{
    public string BaseUrl { get; set; } = "http://localhost:8000";
    public string PipelineRootPath { get; set; } = "../bertimbau-absa";
    public string PythonExecutable { get; set; } = "python";
}

public class AbsaInferenceClient : IAbsaInferenceClient
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    private readonly HttpClient _httpClient;
    private readonly AbsaServiceSettings _settings;

    public AbsaInferenceClient(HttpClient httpClient, IOptions<AbsaServiceSettings> options)
    {
        _httpClient = httpClient;
        _settings = options.Value;
        _httpClient.BaseAddress = new Uri(_settings.BaseUrl.TrimEnd('/') + "/");
    }

    public async Task<AbsaHealthDto> CheckHealthAsync(CancellationToken ct = default)
    {
        try
        {
            using var response = await _httpClient.GetAsync("health", ct);
            if (!response.IsSuccessStatusCode)
                return new AbsaHealthDto("unavailable", false, false, _settings.BaseUrl);

            var payload = await response.Content.ReadFromJsonAsync<AbsaHealthPayload>(JsonOptions, ct);
            return new AbsaHealthDto(
                payload?.Status ?? "unknown",
                payload?.AspectModelLoaded ?? false,
                payload?.SentimentModelLoaded ?? false,
                _settings.BaseUrl);
        }
        catch
        {
            return new AbsaHealthDto("offline", false, false, _settings.BaseUrl);
        }
    }

    public async Task<AbsaAnalysisResponseDto> AnalyzeAsync(string reviewId, string text, string? correlationId = null, CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "api/v1/reviews/analyze")
        {
            Content = JsonContent.Create(new { reviewId, text })
        };

        if (!string.IsNullOrWhiteSpace(correlationId))
            request.Headers.Add("X-Correlation-ID", correlationId);

        using var response = await _httpClient.SendAsync(request, ct);
        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(ct);
            throw new DomainException($"ABSA inference service returned {(int)response.StatusCode}: {body}", "ABSA_SERVICE_ERROR", (int)response.StatusCode);
        }

        var result = await response.Content.ReadFromJsonAsync<AbsaAnalysisResponseDto>(JsonOptions, ct);
        return result ?? throw new DomainException("Empty response from ABSA inference service.", "ABSA_EMPTY_RESPONSE", 502);
    }

    public async Task<DiagnosticSentimentResponseDto> ClassifySentimentAsync(string text, string aspect, string? correlationId = null, CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "api/v1/reviews/classify-sentiment")
        {
            Content = JsonContent.Create(new { text, aspect })
        };

        if (!string.IsNullOrWhiteSpace(correlationId))
            request.Headers.Add("X-Correlation-ID", correlationId);

        using var response = await _httpClient.SendAsync(request, ct);
        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(ct);
            throw new DomainException($"ABSA diagnostic service returned {(int)response.StatusCode}: {body}", "ABSA_DIAGNOSTIC_ERROR", (int)response.StatusCode);
        }

        var result = await response.Content.ReadFromJsonAsync<DiagnosticSentimentResponseDto>(JsonOptions, ct);
        return result ?? throw new DomainException("Empty response from ABSA diagnostic service.", "ABSA_EMPTY_RESPONSE", 502);
    }

    private record AbsaHealthPayload(string Status, bool AspectModelLoaded, bool SentimentModelLoaded);
}
