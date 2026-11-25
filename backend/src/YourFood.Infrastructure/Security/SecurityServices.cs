using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;
using YourFood.Application.Interfaces;
using YourFood.Domain.Entities;
using YourFood.Domain.Repositories;

namespace YourFood.Infrastructure.Security;

public class JwtSettings
{
    public string Issuer { get; set; } = "YourFood.AI";
    public string Audience { get; set; } = "YourFood.Clients";
    public string SigningKey { get; set; } = "YourFood_Fintech_Super_Secret_Key_2026_Minimum_32_Bytes_Long!";
    public int AccessTokenMinutes { get; set; } = 60;
    public int RefreshTokenDays { get; set; } = 14;
}

public class BCryptPasswordHasher : IPasswordHasher
{
    public string Hash(string password) => BCrypt.Net.BCrypt.HashPassword(password, workFactor: 11);

    public bool Verify(string password, string hash) => BCrypt.Net.BCrypt.Verify(password, hash);
}

public class JwtTokenService : IJwtTokenService
{
    private readonly JwtSettings _settings;

    public JwtTokenService(IOptions<JwtSettings> options)
    {
        _settings = options.Value;
    }

    public (string AccessToken, int ExpiresInSeconds) GenerateAccessToken(User user)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_settings.SigningKey));
        var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
        var expiresAt = DateTime.UtcNow.AddMinutes(_settings.AccessTokenMinutes);

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new(JwtRegisteredClaimNames.Email, user.Email),
            new(ClaimTypes.NameIdentifier, user.Id.ToString()),
            new(ClaimTypes.Name, user.FullName),
            new(ClaimTypes.Role, user.Role.ToString()),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
        };

        var token = new JwtSecurityToken(
            issuer: _settings.Issuer,
            audience: _settings.Audience,
            claims: claims,
            notBefore: DateTime.UtcNow,
            expires: expiresAt,
            signingCredentials: credentials);

        var encoded = new JwtSecurityTokenHandler().WriteToken(token);
        return (encoded, _settings.AccessTokenMinutes * 60);
    }

    public (string RawRefreshToken, string TokenHash, DateTime ExpiresAtUtc) GenerateRefreshToken()
    {
        var bytes = RandomNumberGenerator.GetBytes(48);
        var raw = Convert.ToBase64String(bytes).Replace("+", "-").Replace("/", "_").TrimEnd('=');
        return (raw, ComputeHash(raw), DateTime.UtcNow.AddDays(_settings.RefreshTokenDays));
    }

    public string ComputeHash(string value)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }
}

public class AuditTrailService : IAuditTrailService
{
    private readonly IAuditLogRepository _auditLogs;
    private readonly ICorrelationContext _correlation;

    public AuditTrailService(IAuditLogRepository auditLogs, ICorrelationContext correlation)
    {
        _auditLogs = auditLogs;
        _correlation = correlation;
    }

    public async Task RecordAsync(Guid? actorUserId, string action, string entityType, string entityId, object payload, string summary, CancellationToken ct = default)
    {
        var serialized = JsonSerializer.Serialize(payload);
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(serialized))).ToLowerInvariant();
        var log = new AuditLog(actorUserId, action, entityType, entityId, _correlation.CorrelationId, hash, summary);
        await _auditLogs.AddAsync(log, ct);
    }
}
