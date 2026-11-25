using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;
using YourFood.Domain.Repositories;

namespace YourFood.Application.Services;

public interface IOrderService
{
    Task<OrderDto> CreateOrderAsync(Guid customerId, CreateOrderRequest request, CancellationToken ct = default);
    Task<OrderDto> GetOrderAsync(Guid actorId, UserRole actorRole, Guid orderId, CancellationToken ct = default);
    Task<IReadOnlyList<OrderDto>> GetCustomerOrdersAsync(Guid customerId, CancellationToken ct = default);
    Task<IReadOnlyList<OrderDto>> GetMerchantOrdersAsync(Guid ownerId, Guid? storeId, CancellationToken ct = default);
    Task<OrderDto> TransitionOrderAsync(Guid actorId, UserRole actorRole, Guid orderId, TransitionOrderStatusRequest request, CancellationToken ct = default);
}

public class OrderService : IOrderService
{
    private readonly IOrderRepository _orders;
    private readonly IStoreRepository _stores;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IAuditTrailService _audit;

    public OrderService(IOrderRepository orders, IStoreRepository stores, IUnitOfWork unitOfWork, IAuditTrailService audit)
    {
        _orders = orders;
        _stores = stores;
        _unitOfWork = unitOfWork;
        _audit = audit;
    }

    public async Task<OrderDto> CreateOrderAsync(Guid customerId, CreateOrderRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.DeliveryAddress))
            throw new DomainException("Delivery address is required.", "MISSING_DELIVERY_ADDRESS");

        var store = await _stores.GetByIdWithMenuAsync(request.StoreId, ct)
            ?? throw new NotFoundException(nameof(Store), request.StoreId);

        if (!store.IsOpen)
            throw new DomainException("Store is currently closed.", "STORE_CLOSED");

        var menuLookup = store.MenuItems.ToDictionary(m => m.Id);
        var orderItems = new List<OrderItem>();

        foreach (var itemInput in request.Items)
        {
            if (!menuLookup.TryGetValue(itemInput.MenuItemId, out var menuItem))
                throw new DomainException($"Menu item '{itemInput.MenuItemId}' does not belong to store '{store.Name}'.", "INVALID_MENU_ITEM");

            if (!menuItem.IsAvailable)
                throw new DomainException($"Menu item '{menuItem.Name}' is currently unavailable.", "MENU_ITEM_UNAVAILABLE");

            orderItems.Add(new OrderItem(menuItem.Id, menuItem.Name, menuItem.Price, itemInput.Quantity));
        }

        var order = new Order(customerId, store.Id, request.DeliveryAddress, store.DeliveryFee, request.Notes, orderItems);

        await _orders.AddAsync(order, ct);
        await _audit.RecordAsync(customerId, "ORDER_CREATED", nameof(Order), order.Id.ToString(), new { store.Id, order.TotalAmount }, $"Order placed at '{store.Name}' totaling {order.TotalAmount:F2} BRL", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        var loaded = await _orders.GetByIdDetailedAsync(order.Id, ct) ?? order;
        return MapOrder(loaded, store.Name);
    }

    public async Task<OrderDto> GetOrderAsync(Guid actorId, UserRole actorRole, Guid orderId, CancellationToken ct = default)
    {
        var order = await _orders.GetByIdDetailedAsync(orderId, ct)
            ?? throw new NotFoundException(nameof(Order), orderId);

        EnsureOrderAccess(order, actorId, actorRole);
        return MapOrder(order, order.Store?.Name ?? string.Empty);
    }

    public async Task<IReadOnlyList<OrderDto>> GetCustomerOrdersAsync(Guid customerId, CancellationToken ct = default)
    {
        var orders = await _orders.GetByCustomerIdAsync(customerId, ct);
        return orders.Select(o => MapOrder(o, o.Store?.Name ?? string.Empty)).ToList();
    }

    public async Task<IReadOnlyList<OrderDto>> GetMerchantOrdersAsync(Guid ownerId, Guid? storeId, CancellationToken ct = default)
    {
        IReadOnlyList<Order> orders;
        if (storeId.HasValue)
        {
            var store = await _stores.GetByIdAsync(storeId.Value, ct)
                ?? throw new NotFoundException(nameof(Store), storeId.Value);

            if (store.OwnerId != ownerId)
                throw new ForbiddenException("Store does not belong to current merchant.");

            orders = await _orders.GetByStoreIdAsync(storeId.Value, ct);
        }
        else
        {
            orders = await _orders.GetByOwnerIdAsync(ownerId, ct);
        }

        return orders.Select(o => MapOrder(o, o.Store?.Name ?? string.Empty)).ToList();
    }

    public async Task<OrderDto> TransitionOrderAsync(Guid actorId, UserRole actorRole, Guid orderId, TransitionOrderStatusRequest request, CancellationToken ct = default)
    {
        var order = await _orders.GetByIdDetailedAsync(orderId, ct)
            ?? throw new NotFoundException(nameof(Order), orderId);

        if (actorRole == UserRole.Customer)
        {
            if (order.CustomerId != actorId)
                throw new ForbiddenException("Cannot modify another customer's order.");

            var customerAllowed = request.NextStatus is OrderStatus.Confirmed or OrderStatus.Cancelled;
            if (!customerAllowed)
                throw new ForbiddenException("Customers may only confirm payment or cancel an order.");
        }
        else if (actorRole == UserRole.StoreOwner)
        {
            if (order.Store.OwnerId != actorId)
                throw new ForbiddenException("Order belongs to another store.");
        }

        order.TransitionTo(request.NextStatus, actorId, request.Reason);
        _orders.Update(order);

        await _audit.RecordAsync(
            actorId,
            "ORDER_STATE_TRANSITION",
            nameof(Order),
            order.Id.ToString(),
            new { order.Status, request.Reason },
            $"Order moved to {order.Status}",
            ct);

        await _unitOfWork.SaveChangesAsync(ct);

        return MapOrder(order, order.Store?.Name ?? string.Empty);
    }

    private static void EnsureOrderAccess(Order order, Guid actorId, UserRole actorRole)
    {
        if (actorRole == UserRole.Admin) return;
        if (order.CustomerId == actorId) return;
        if (actorRole == UserRole.StoreOwner && order.Store?.OwnerId == actorId) return;

        throw new ForbiddenException("You do not have access to this order.");
    }

    private static OrderDto MapOrder(Order order, string storeName) =>
        new(
            order.Id,
            order.CustomerId,
            order.StoreId,
            storeName,
            order.DeliveryAddress,
            order.Status.ToString(),
            order.GetAllowedNextStatuses().Select(s => s.ToString()).ToList(),
            order.SubtotalAmount,
            order.DeliveryFeeAmount,
            order.TotalAmount,
            order.CurrencyCode,
            order.Notes,
            order.Review is not null,
            order.CreatedAtUtc,
            order.Items.Select(i => new OrderItemDto(i.Id, i.MenuItemId, i.ItemNameSnapshot, i.UnitPriceSnapshot, i.Quantity, i.LineTotal)).ToList(),
            order.StateHistory.OrderBy(h => h.CreatedAtUtc).Select(h => new OrderStateTransitionDto(h.Id, h.FromStatus?.ToString(), h.ToStatus.ToString(), h.ActorUserId, h.Reason, h.CreatedAtUtc)).ToList(),
            order.LedgerEntries.OrderBy(l => l.CreatedAtUtc).Select(l => new LedgerEntryDto(l.Id, l.EntryType.ToString(), l.Amount, l.CurrencyCode, l.Description, l.CreatedAtUtc)).ToList());
}
