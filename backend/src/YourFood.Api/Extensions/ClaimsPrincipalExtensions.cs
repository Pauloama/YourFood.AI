using System.Security.Claims;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;

namespace YourFood.Api.Extensions;

public static class ClaimsPrincipalExtensions
{
    public static Guid GetUserId(this ClaimsPrincipal user)
    {
        var raw = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? user.FindFirstValue("sub");
        if (!Guid.TryParse(raw, out var id))
            throw new DomainException("Invalid authentication token subject.", "INVALID_TOKEN", 401);
        return id;
    }

    public static UserRole GetUserRole(this ClaimsPrincipal user)
    {
        var raw = user.FindFirstValue(ClaimTypes.Role);
        if (!Enum.TryParse<UserRole>(raw, true, out var role))
            throw new DomainException("Invalid authentication token role.", "INVALID_ROLE", 401);
        return role;
    }
}
