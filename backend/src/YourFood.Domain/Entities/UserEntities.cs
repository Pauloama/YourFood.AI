using YourFood.Domain.Enums;

namespace YourFood.Domain.Entities;

public class User : BaseEntity
{
    public string FullName { get; private set; } = string.Empty;
    public string Email { get; private set; } = string.Empty;
    public string PasswordHash { get; private set; } = string.Empty;
    public UserRole Role { get; private set; }
    public string? OAuthProvider { get; private set; }
    public string? OAuthSubject { get; private set; }
    public bool IsActive { get; private set; } = true;

    public ICollection<Store> Stores { get; private set; } = new List<Store>();
    public ICollection<Order> Orders { get; private set; } = new List<Order>();
    public ICollection<RefreshToken> RefreshTokens { get; private set; } = new List<RefreshToken>();

    private User() { }

    public User(string fullName, string email, string passwordHash, UserRole role, string? oauthProvider = null, string? oauthSubject = null)
    {
        FullName = fullName.Trim();
        Email = email.Trim().ToLowerInvariant();
        PasswordHash = passwordHash;
        Role = role;
        OAuthProvider = oauthProvider;
        OAuthSubject = oauthSubject;
    }

    public void LinkOAuthAccount(string provider, string subject)
    {
        OAuthProvider = provider;
        OAuthSubject = subject;
        Touch();
    }

    public void UpdateRole(UserRole role)
    {
        Role = role;
        Touch();
    }
}

public class RefreshToken : BaseEntity
{
    public Guid UserId { get; private set; }
    public string TokenHash { get; private set; } = string.Empty;
    public DateTime ExpiresAtUtc { get; private set; }
    public DateTime? RevokedAtUtc { get; private set; }
    public string? ReplacedByTokenHash { get; private set; }
    public User User { get; private set; } = null!;

    private RefreshToken() { }

    public RefreshToken(Guid userId, string tokenHash, DateTime expiresAtUtc)
    {
        UserId = userId;
        TokenHash = tokenHash;
        ExpiresAtUtc = expiresAtUtc;
    }

    public bool IsActive => RevokedAtUtc is null && DateTime.UtcNow < ExpiresAtUtc;

    public void Revoke(string? replacedByTokenHash = null)
    {
        RevokedAtUtc = DateTime.UtcNow;
        ReplacedByTokenHash = replacedByTokenHash;
        Touch();
    }
}

public class OAuthAuthorizationCode : BaseEntity
{
    public string Code { get; private set; } = string.Empty;
    public string ClientId { get; private set; } = string.Empty;
    public string RedirectUri { get; private set; } = string.Empty;
    public string Scope { get; private set; } = string.Empty;
    public string? CodeChallenge { get; private set; }
    public Guid UserId { get; private set; }
    public DateTime ExpiresAtUtc { get; private set; }
    public bool IsConsumed { get; private set; }

    private OAuthAuthorizationCode() { }

    public OAuthAuthorizationCode(string code, string clientId, string redirectUri, string scope, Guid userId, DateTime expiresAtUtc, string? codeChallenge = null)
    {
        Code = code;
        ClientId = clientId;
        RedirectUri = redirectUri;
        Scope = scope;
        UserId = userId;
        ExpiresAtUtc = expiresAtUtc;
        CodeChallenge = codeChallenge;
    }

    public bool IsValid => !IsConsumed && DateTime.UtcNow < ExpiresAtUtc;

    public void Consume()
    {
        IsConsumed = true;
        Touch();
    }
}
