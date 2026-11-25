using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using YourFood.Api.Extensions;
using YourFood.Application.DTOs;
using YourFood.Application.Services;

namespace YourFood.Api.Controllers;

[ApiController]
[Route("api/v1/orders")]
[Authorize]
public class OrdersController : ControllerBase
{
    private readonly IOrderService _orderService;

    public OrdersController(IOrderService orderService)
    {
        _orderService = orderService;
    }

    [HttpPost]
    [Authorize(Roles = "Customer,Admin")]
    public async Task<ActionResult<OrderDto>> Create([FromBody] CreateOrderRequest request, CancellationToken ct)
    {
        var created = await _orderService.CreateOrderAsync(User.GetUserId(), request, ct);
        return CreatedAtAction(nameof(GetById), new { orderId = created.Id }, created);
    }

    [HttpGet("{orderId:guid}")]
    public async Task<ActionResult<OrderDto>> GetById(Guid orderId, CancellationToken ct) =>
        Ok(await _orderService.GetOrderAsync(User.GetUserId(), User.GetUserRole(), orderId, ct));

    [HttpGet("my")]
    public async Task<ActionResult<IReadOnlyList<OrderDto>>> GetMyOrders(CancellationToken ct) =>
        Ok(await _orderService.GetCustomerOrdersAsync(User.GetUserId(), ct));

    [HttpGet("merchant")]
    [Authorize(Roles = "StoreOwner,Admin")]
    public async Task<ActionResult<IReadOnlyList<OrderDto>>> GetMerchantOrders([FromQuery] Guid? storeId, CancellationToken ct) =>
        Ok(await _orderService.GetMerchantOrdersAsync(User.GetUserId(), storeId, ct));

    [HttpPatch("{orderId:guid}/status")]
    public async Task<ActionResult<OrderDto>> TransitionStatus(Guid orderId, [FromBody] TransitionOrderStatusRequest request, CancellationToken ct) =>
        Ok(await _orderService.TransitionOrderAsync(User.GetUserId(), User.GetUserRole(), orderId, request, ct));
}
