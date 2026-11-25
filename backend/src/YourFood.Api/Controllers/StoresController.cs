using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using YourFood.Api.Extensions;
using YourFood.Application.DTOs;
using YourFood.Application.Services;

namespace YourFood.Api.Controllers;

[ApiController]
[Route("api/v1/stores")]
public class StoresController : ControllerBase
{
    private readonly IStoreService _storeService;

    public StoresController(IStoreService storeService)
    {
        _storeService = storeService;
    }

    [HttpGet]
    [AllowAnonymous]
    public async Task<ActionResult<IReadOnlyList<StoreDto>>> List([FromQuery] string? search, [FromQuery] string? category, CancellationToken ct) =>
        Ok(await _storeService.ListStoresAsync(search, category, ct));

    [HttpGet("{storeId:guid}")]
    [AllowAnonymous]
    public async Task<ActionResult<StoreDto>> GetById(Guid storeId, CancellationToken ct) =>
        Ok(await _storeService.GetStoreAsync(storeId, ct));

    [HttpGet("mine")]
    [Authorize(Roles = "StoreOwner,Admin")]
    public async Task<ActionResult<IReadOnlyList<StoreDto>>> GetMine(CancellationToken ct) =>
        Ok(await _storeService.GetOwnerStoresAsync(User.GetUserId(), ct));

    [HttpPost]
    [Authorize(Roles = "StoreOwner,Admin")]
    public async Task<ActionResult<StoreDto>> Create([FromBody] CreateStoreRequest request, CancellationToken ct)
    {
        var created = await _storeService.CreateStoreAsync(User.GetUserId(), request, ct);
        return CreatedAtAction(nameof(GetById), new { storeId = created.Id }, created);
    }

    [HttpPut("{storeId:guid}")]
    [Authorize(Roles = "StoreOwner,Admin")]
    public async Task<ActionResult<StoreDto>> Update(Guid storeId, [FromBody] UpdateStoreRequest request, CancellationToken ct) =>
        Ok(await _storeService.UpdateStoreAsync(User.GetUserId(), User.GetUserRole(), storeId, request, ct));

    [HttpPost("{storeId:guid}/items")]
    [Authorize(Roles = "StoreOwner,Admin")]
    public async Task<ActionResult<MenuItemDto>> AddItem(Guid storeId, [FromBody] CreateMenuItemRequest request, CancellationToken ct) =>
        Ok(await _storeService.AddMenuItemAsync(User.GetUserId(), User.GetUserRole(), storeId, request, ct));

    [HttpPut("items/{menuItemId:guid}")]
    [Authorize(Roles = "StoreOwner,Admin")]
    public async Task<ActionResult<MenuItemDto>> UpdateItem(Guid menuItemId, [FromBody] UpdateMenuItemRequest request, CancellationToken ct) =>
        Ok(await _storeService.UpdateMenuItemAsync(User.GetUserId(), User.GetUserRole(), menuItemId, request, ct));
}
