using System.Security.Cryptography;
using System.Text;
using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;
using YourFood.Domain.Repositories;

namespace YourFood.Application.Services;

public interface IAuthService
{
    Task<AuthTokenResponse> RegisterAsync(RegisterRequest request, CancellationToken ct = default);
    Task<AuthTokenResponse> LoginAsync(LoginRequest request, CancellationToken ct = default);
    Task<AuthTokenResponse> RefreshAsync(RefreshTokenRequest request, CancellationToken ct = default);
    Task<OAuthAuthorizeResponse> CreateAuthorizationCodeAsync(Guid userId, OAuthAuthorizeRequest request, CancellationToken ct = default);
    Task<AuthTokenResponse> ExchangeOAuthTokenAsync(OAuthTokenRequest request, CancellationToken ct = default);
    Task<AuthTokenResponse> ExternalOAuthLoginAsync(OAuthExternalLoginRequest request, CancellationToken ct = default);
    Task<UserSummaryDto> GetProfileAsync(Guid userId, CancellationToken ct = default);
}

public class AuthService : IAuthService
{
    private readonly IUserRepository _users;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IPasswordHasher _passwordHasher;
    private readonly IJwtTokenService _jwtTokenService;
    private readonly IAuditTrailService _audit;

    public AuthService(
        IUserRepository users,
        IUnitOfWork unitOfWork,
        IPasswordHasher passwordHasher,
        IJwtTokenService jwtTokenService,
        IAuditTrailService audit)
    {
        _users = users;
        _unitOfWork = unitOfWork;
        _passwordHasher = passwordHasher;
        _jwtTokenService = jwtTokenService;
        _audit = audit;
    }

    public async Task<AuthTokenResponse> RegisterAsync(RegisterRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.FullName) || string.IsNullOrWhiteSpace(request.Email) || request.Password.Length < 6)
            throw new DomainException("Invalid registration credentials.", "INVALID_REGISTRATION");

        var existing = await _users.GetByEmailAsync(request.Email.Trim().ToLowerInvariant(), ct);
        if (existing is not null)
            throw new ConflictException("Email is already registered.");

        var passwordHash = _passwordHasher.Hash(request.Password);
        var user = new User(request.FullName, request.Email, passwordHash, request.Role);

        await _users.AddAsync(user, ct);
        var response = await IssueTokensAsync(user, ct);
        await _audit.RecordAsync(user.Id, "USER_REGISTERED", nameof(User), user.Id.ToString(), new { user.Email, user.Role }, "New user registered", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return response;
    }

    public async Task<AuthTokenResponse> LoginAsync(LoginRequest request, CancellationToken ct = default)
    {
        var user = await _users.GetByEmailAsync(request.Email.Trim().ToLowerInvariant(), ct);
        if (user is null || !user.IsActive || !_passwordHasher.Verify(request.Password, user.PasswordHash))
            throw new DomainException("Invalid email or password.", "INVALID_CREDENTIALS", 401);

        var response = await IssueTokensAsync(user, ct);
        await _audit.RecordAsync(user.Id, "USER_LOGIN", nameof(User), user.Id.ToString(), new { user.Email }, "User authenticated via password", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return response;
    }

    public async Task<AuthTokenResponse> RefreshAsync(RefreshTokenRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.RefreshToken))
            throw new DomainException("Refresh token is required.", "INVALID_REFRESH_TOKEN", 401);

        var hash = _jwtTokenService.ComputeHash(request.RefreshToken);
        var stored = await _users.GetRefreshTokenByHashAsync(hash, ct);

        if (stored is null || !stored.IsActive)
            throw new DomainException("Refresh token is invalid or expired.", "INVALID_REFRESH_TOKEN", 401);

        var user = await _users.GetByIdAsync(stored.UserId, ct)
            ?? throw new NotFoundException(nameof(User), stored.UserId);

        var (rawNew, newHash, newExpiry) = _jwtTokenService.GenerateRefreshToken();
        stored.Revoke(newHash);
        await _users.AddRefreshTokenAsync(new RefreshToken(user.Id, newHash, newExpiry), ct);

        var (accessToken, expiresIn) = _jwtTokenService.GenerateAccessToken(user);
        await _unitOfWork.SaveChangesAsync(ct);

        return new AuthTokenResponse(accessToken, rawNew, "Bearer", expiresIn, MapUser(user));
    }

    public async Task<OAuthAuthorizeResponse> CreateAuthorizationCodeAsync(Guid userId, OAuthAuthorizeRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.ClientId) || string.IsNullOrWhiteSpace(request.RedirectUri))
            throw new DomainException("ClientId and RedirectUri are required.", "INVALID_OAUTH_REQUEST");

        var codeBytes = RandomNumberGenerator.GetBytes(32);
        var code = Convert.ToBase64String(codeBytes).Replace("+", "-").Replace("/", "_").TrimEnd('=');
        var expiresAt = DateTime.UtcNow.AddMinutes(5);

        var authCode = new OAuthAuthorizationCode(
            code,
            request.ClientId,
            request.RedirectUri,
            string.IsNullOrWhiteSpace(request.Scope) ? "delivery.read delivery.write absa.read" : request.Scope,
            userId,
            expiresAt,
            request.CodeChallenge);

        await _users.AddAuthorizationCodeAsync(authCode, ct);
        await _audit.RecordAsync(userId, "OAUTH2_AUTHORIZE", nameof(OAuthAuthorizationCode), authCode.Id.ToString(), new { request.ClientId, request.Scope }, "OAuth2 authorization code issued", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return new OAuthAuthorizeResponse(code, request.RedirectUri, authCode.Scope, expiresAt);
    }

    public async Task<AuthTokenResponse> ExchangeOAuthTokenAsync(OAuthTokenRequest request, CancellationToken ct = default)
    {
        if (string.Equals(request.GrantType, "refresh_token", StringComparison.OrdinalIgnoreCase))
            return await RefreshAsync(new RefreshTokenRequest(request.RefreshToken ?? string.Empty), ct);

        if (!string.Equals(request.GrantType, "authorization_code", StringComparison.OrdinalIgnoreCase))
            throw new DomainException("Unsupported OAuth2 grant_type.", "UNSUPPORTED_GRANT_TYPE");

        var authCode = await _users.GetAuthorizationCodeAsync(request.Code ?? string.Empty, ct);
        if (authCode is null || !authCode.IsValid)
            throw new DomainException("Authorization code is invalid or expired.", "INVALID_GRANT", 401);

        if (!string.Equals(authCode.ClientId, request.ClientId, StringComparison.Ordinal) ||
            !string.Equals(authCode.RedirectUri, request.RedirectUri, StringComparison.Ordinal))
            throw new DomainException("Client or redirect_uri mismatch.", "INVALID_CLIENT", 401);

        if (!string.IsNullOrEmpty(authCode.CodeChallenge))
        {
            if (string.IsNullOrEmpty(request.CodeVerifier))
                throw new DomainException("PKCE code_verifier is required.", "INVALID_PKCE", 401);

            var verifierHash = SHA256.HashData(Encoding.UTF8.GetBytes(request.CodeVerifier));
            var computedChallenge = Convert.ToBase64String(verifierHash).Replace("+", "-").Replace("/", "_").TrimEnd('=');
            if (!string.Equals(computedChallenge, authCode.CodeChallenge, StringComparison.Ordinal))
                throw new DomainException("Invalid PKCE code_verifier.", "INVALID_PKCE", 401);
        }

        authCode.Consume();
        var user = await _users.GetByIdAsync(authCode.UserId, ct)
            ?? throw new NotFoundException(nameof(User), authCode.UserId);

        var response = await IssueTokensAsync(user, ct);
        await _audit.RecordAsync(user.Id, "OAUTH2_TOKEN_EXCHANGE", nameof(User), user.Id.ToString(), new { authCode.ClientId }, "OAuth2 authorization code exchanged for JWT", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return response;
    }

    public async Task<AuthTokenResponse> ExternalOAuthLoginAsync(OAuthExternalLoginRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.Provider) || string.IsNullOrWhiteSpace(request.ExternalSubject) || string.IsNullOrWhiteSpace(request.Email))
            throw new DomainException("Provider, ExternalSubject and Email are required.", "INVALID_OAUTH_EXTERNAL");

        var provider = request.Provider.Trim().ToLowerInvariant();
        var user = await _users.GetByOAuthAsync(provider, request.ExternalSubject, ct)
            ?? await _users.GetByEmailAsync(request.Email.Trim().ToLowerInvariant(), ct);

        if (user is null)
        {
            var generatedPassword = Convert.ToBase64String(RandomNumberGenerator.GetBytes(32));
            user = new User(
                request.FullName,
                request.Email,
                _passwordHasher.Hash(generatedPassword),
                request.PreferredRole ?? UserRole.Customer,
                provider,
                request.ExternalSubject);

            await _users.AddAsync(user, ct);
        }
        else if (string.IsNullOrEmpty(user.OAuthSubject))
        {
            user.LinkOAuthAccount(provider, request.ExternalSubject);
            _users.Update(user);
        }

        var response = await IssueTokensAsync(user, ct);
        await _audit.RecordAsync(user.Id, "OAUTH2_EXTERNAL_LOGIN", nameof(User), user.Id.ToString(), new { provider }, "User authenticated via OAuth2 provider", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return response;
    }

    public async Task<UserSummaryDto> GetProfileAsync(Guid userId, CancellationToken ct = default)
    {
        var user = await _users.GetByIdAsync(userId, ct)
            ?? throw new NotFoundException(nameof(User), userId);
        return MapUser(user);
    }

    private async Task<AuthTokenResponse> IssueTokensAsync(User user, CancellationToken ct)
    {
        var (accessToken, expiresIn) = _jwtTokenService.GenerateAccessToken(user);
        var (rawRefresh, refreshHash, refreshExpiry) = _jwtTokenService.GenerateRefreshToken();
        await _users.AddRefreshTokenAsync(new RefreshToken(user.Id, refreshHash, refreshExpiry), ct);
        return new AuthTokenResponse(accessToken, rawRefresh, "Bearer", expiresIn, MapUser(user));
    }

    private static UserSummaryDto MapUser(User user) =>
        new(user.Id, user.FullName, user.Email, user.Role.ToString(), user.OAuthProvider);
}
