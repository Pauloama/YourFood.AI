using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using YourFood.Api.Extensions;
using YourFood.Application.DTOs;
using YourFood.Application.Services;

namespace YourFood.Api.Controllers;

[ApiController]
[Route("api/v1/auth")]
public class AuthController : ControllerBase
{
    private readonly IAuthService _authService;

    public AuthController(IAuthService authService)
    {
        _authService = authService;
    }

    [HttpPost("register")]
    [AllowAnonymous]
    public async Task<ActionResult<AuthTokenResponse>> Register([FromBody] RegisterRequest request, CancellationToken ct) =>
        Ok(await _authService.RegisterAsync(request, ct));

    [HttpPost("login")]
    [AllowAnonymous]
    public async Task<ActionResult<AuthTokenResponse>> Login([FromBody] LoginRequest request, CancellationToken ct) =>
        Ok(await _authService.LoginAsync(request, ct));

    [HttpPost("refresh")]
    [AllowAnonymous]
    public async Task<ActionResult<AuthTokenResponse>> Refresh([FromBody] RefreshTokenRequest request, CancellationToken ct) =>
        Ok(await _authService.RefreshAsync(request, ct));

    [HttpPost("oauth2/authorize")]
    [Authorize]
    public async Task<ActionResult<OAuthAuthorizeResponse>> Authorize([FromBody] OAuthAuthorizeRequest request, CancellationToken ct) =>
        Ok(await _authService.CreateAuthorizationCodeAsync(User.GetUserId(), request, ct));

    [HttpPost("oauth2/token")]
    [AllowAnonymous]
    public async Task<ActionResult<AuthTokenResponse>> Token([FromBody] OAuthTokenRequest request, CancellationToken ct) =>
        Ok(await _authService.ExchangeOAuthTokenAsync(request, ct));

    [HttpPost("oauth2/external")]
    [AllowAnonymous]
    public async Task<ActionResult<AuthTokenResponse>> ExternalLogin([FromBody] OAuthExternalLoginRequest request, CancellationToken ct) =>
        Ok(await _authService.ExternalOAuthLoginAsync(request, ct));

    [HttpGet("me")]
    [Authorize]
    public async Task<ActionResult<UserSummaryDto>> Me(CancellationToken ct) =>
        Ok(await _authService.GetProfileAsync(User.GetUserId(), ct));
}
