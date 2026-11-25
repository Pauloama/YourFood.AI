using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using YourFood.Application.Interfaces;
using YourFood.Domain.Entities;
using YourFood.Domain.Exceptions;
using YourFood.Domain.Repositories;

namespace YourFood.Api.Middleware;

public class HttpCorrelationContext : ICorrelationContext
{
    private readonly IHttpContextAccessor _accessor;

    public HttpCorrelationContext(IHttpContextAccessor accessor)
    {
        _accessor = accessor;
    }

    public string CorrelationId =>
        _accessor.HttpContext?.Items["CorrelationId"]?.ToString() ?? Guid.NewGuid().ToString("N");
}

public class CorrelationIdMiddleware
{
    private const string HeaderName = "X-Correlation-ID";
    private readonly RequestDelegate _next;

    public CorrelationIdMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var correlationId = context.Request.Headers.TryGetValue(HeaderName, out var existing) && !string.IsNullOrWhiteSpace(existing)
            ? existing.ToString()
            : Guid.NewGuid().ToString("N");

        context.Items["CorrelationId"] = correlationId;
        context.Response.OnStarting(() =>
        {
            context.Response.Headers[HeaderName] = correlationId;
            return Task.CompletedTask;
        });

        await _next(context);
    }
}

public class GlobalExceptionMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<GlobalExceptionMiddleware> _logger;

    public GlobalExceptionMiddleware(RequestDelegate next, ILogger<GlobalExceptionMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (DomainException ex)
        {
            context.Response.StatusCode = ex.StatusCode;
            context.Response.ContentType = "application/json";
            var payload = new
            {
                code = ex.Code,
                message = ex.Message,
                correlationId = context.Items["CorrelationId"]?.ToString()
            };
            await context.Response.WriteAsync(JsonSerializer.Serialize(payload));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled exception on {Path}", context.Request.Path);
            context.Response.StatusCode = 500;
            context.Response.ContentType = "application/json";
            var payload = new
            {
                code = "INTERNAL_SERVER_ERROR",
                message = "An unexpected error occurred.",
                correlationId = context.Items["CorrelationId"]?.ToString()
            };
            await context.Response.WriteAsync(JsonSerializer.Serialize(payload));
        }
    }
}

public class IdempotencyMiddleware
{
    private const string HeaderName = "Idempotency-Key";
    private readonly RequestDelegate _next;

    public IdempotencyMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context, IIdempotencyRepository repository, IUnitOfWork unitOfWork)
    {
        if (!HttpMethods.IsPost(context.Request.Method) ||
            !context.Request.Headers.TryGetValue(HeaderName, out var rawKey) ||
            string.IsNullOrWhiteSpace(rawKey))
        {
            await _next(context);
            return;
        }

        var key = rawKey.ToString().Trim();
        var path = context.Request.Path.Value ?? string.Empty;

        context.Request.EnableBuffering();
        using var reader = new StreamReader(context.Request.Body, Encoding.UTF8, leaveOpen: true);
        var requestBody = await reader.ReadToEndAsync();
        context.Request.Body.Position = 0;

        var requestHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(requestBody))).ToLowerInvariant();
        var existing = await repository.GetByKeyAsync(key, path);

        if (existing is not null)
        {
            if (!string.Equals(existing.RequestHash, requestHash, StringComparison.Ordinal))
            {
                context.Response.StatusCode = StatusCodes.Status409Conflict;
                context.Response.ContentType = "application/json";
                await context.Response.WriteAsync(JsonSerializer.Serialize(new
                {
                    code = "IDEMPOTENCY_CONFLICT",
                    message = "Idempotency-Key was reused with a different request payload."
                }));
                return;
            }

            context.Response.StatusCode = existing.ResponseStatusCode;
            context.Response.ContentType = "application/json";
            context.Response.Headers["X-Idempotency-Replayed"] = "true";
            await context.Response.WriteAsync(existing.ResponseBody);
            return;
        }

        var originalBody = context.Response.Body;
        using var memStream = new MemoryStream();
        context.Response.Body = memStream;

        await _next(context);

        memStream.Position = 0;
        var responseText = await new StreamReader(memStream, Encoding.UTF8).ReadToEndAsync();
        memStream.Position = 0;
        await memStream.CopyToAsync(originalBody);
        context.Response.Body = originalBody;

        if (context.Response.StatusCode is >= 200 and < 300)
        {
            await repository.AddAsync(new IdempotencyRecord(key, path, requestHash, context.Response.StatusCode, responseText, TimeSpan.FromHours(24)));
            await unitOfWork.SaveChangesAsync();
        }
    }
}
