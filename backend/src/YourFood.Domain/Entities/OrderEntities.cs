using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;

namespace YourFood.Domain.Entities;

public class Order : BaseEntity
{
    private static readonly IReadOnlyDictionary<OrderStatus, OrderStatus[]> AllowedTransitions =
        new Dictionary<OrderStatus, OrderStatus[]>
        {
            [OrderStatus.PendingPayment] = [OrderStatus.Confirmed, OrderStatus.Cancelled],
            [OrderStatus.Confirmed] = [OrderStatus.Preparing, OrderStatus.Cancelled],
            [OrderStatus.Preparing] = [OrderStatus.ReadyForPickup, OrderStatus.Cancelled],
            [OrderStatus.ReadyForPickup] = [OrderStatus.OutForDelivery, OrderStatus.Cancelled],
            [OrderStatus.OutForDelivery] = [OrderStatus.Delivered, OrderStatus.Cancelled],
            [OrderStatus.Delivered] = [],
            [OrderStatus.Cancelled] = []
        };

    public Guid CustomerId { get; private set; }
    public Guid StoreId { get; private set; }
    public string DeliveryAddress { get; private set; } = string.Empty;
    public OrderStatus Status { get; private set; }
    public decimal SubtotalAmount { get; private set; }
    public decimal DeliveryFeeAmount { get; private set; }
    public decimal TotalAmount { get; private set; }
    public string CurrencyCode { get; private set; } = "BRL";
    public string? Notes { get; private set; }

    public User Customer { get; private set; } = null!;
    public Store Store { get; private set; } = null!;
    public ICollection<OrderItem> Items { get; private set; } = new List<OrderItem>();
    public ICollection<OrderStateTransition> StateHistory { get; private set; } = new List<OrderStateTransition>();
    public ICollection<LedgerEntry> LedgerEntries { get; private set; } = new List<LedgerEntry>();
    public Review? Review { get; private set; }

    private Order() { }

    public Order(Guid customerId, Guid storeId, string deliveryAddress, decimal deliveryFeeAmount, string? notes, IEnumerable<OrderItem> items)
    {
        var itemList = items.ToList();
        if (itemList.Count == 0)
            throw new DomainException("Order must contain at least one item.", "EMPTY_ORDER");

        CustomerId = customerId;
        StoreId = storeId;
        DeliveryAddress = deliveryAddress.Trim();
        Notes = string.IsNullOrWhiteSpace(notes) ? null : notes.Trim();
        DeliveryFeeAmount = decimal.Round(deliveryFeeAmount, 2, MidpointRounding.ToEven);
        SubtotalAmount = decimal.Round(itemList.Sum(i => i.LineTotal), 2, MidpointRounding.ToEven);
        TotalAmount = decimal.Round(SubtotalAmount + DeliveryFeeAmount, 2, MidpointRounding.ToEven);
        Status = OrderStatus.PendingPayment;

        foreach (var item in itemList)
        {
            item.AttachToOrder(Id);
            Items.Add(item);
        }

        StateHistory.Add(new OrderStateTransition(Id, null, OrderStatus.PendingPayment, customerId, "Order created"));
        LedgerEntries.Add(new LedgerEntry(Id, LedgerEntryType.OrderCharge, TotalAmount, CurrencyCode, "Initial order charge"));
    }

    public bool CanTransitionTo(OrderStatus nextStatus) =>
        AllowedTransitions.TryGetValue(Status, out var targets) && targets.Contains(nextStatus);

    public IReadOnlyList<OrderStatus> GetAllowedNextStatuses() =>
        AllowedTransitions.TryGetValue(Status, out var targets) ? targets : [];

    public void TransitionTo(OrderStatus nextStatus, Guid actorId, string? reason = null)
    {
        if (!CanTransitionTo(nextStatus))
            throw new DomainException($"Invalid order state transition from {Status} to {nextStatus}.", "INVALID_STATE_TRANSITION");

        var previous = Status;
        Status = nextStatus;
        StateHistory.Add(new OrderStateTransition(Id, previous, nextStatus, actorId, reason));

        if (nextStatus == OrderStatus.Cancelled)
        {
            LedgerEntries.Add(new LedgerEntry(Id, LedgerEntryType.OrderRefund, -TotalAmount, CurrencyCode, reason ?? "Order cancelled refund"));
        }
        else if (nextStatus == OrderStatus.Delivered)
        {
            LedgerEntries.Add(new LedgerEntry(Id, LedgerEntryType.MerchantSettlement, SubtotalAmount, CurrencyCode, "Merchant settlement on delivery"));
        }

        Touch();
    }
}

public class OrderItem : BaseEntity
{
    public Guid OrderId { get; private set; }
    public Guid MenuItemId { get; private set; }
    public string ItemNameSnapshot { get; private set; } = string.Empty;
    public decimal UnitPriceSnapshot { get; private set; }
    public int Quantity { get; private set; }
    public decimal LineTotal { get; private set; }

    public Order Order { get; private set; } = null!;

    private OrderItem() { }

    public OrderItem(Guid menuItemId, string itemNameSnapshot, decimal unitPriceSnapshot, int quantity)
    {
        if (quantity <= 0)
            throw new DomainException("Item quantity must be at least 1.", "INVALID_QUANTITY");
        if (unitPriceSnapshot <= 0)
            throw new DomainException("Unit price must be greater than zero.", "INVALID_UNIT_PRICE");

        MenuItemId = menuItemId;
        ItemNameSnapshot = itemNameSnapshot.Trim();
        UnitPriceSnapshot = decimal.Round(unitPriceSnapshot, 2, MidpointRounding.ToEven);
        Quantity = quantity;
        LineTotal = decimal.Round(UnitPriceSnapshot * Quantity, 2, MidpointRounding.ToEven);
    }

    internal void AttachToOrder(Guid orderId)
    {
        OrderId = orderId;
    }
}

public class OrderStateTransition : BaseEntity
{
    public Guid OrderId { get; private set; }
    public OrderStatus? FromStatus { get; private set; }
    public OrderStatus ToStatus { get; private set; }
    public Guid ActorUserId { get; private set; }
    public string? Reason { get; private set; }

    public Order Order { get; private set; } = null!;

    private OrderStateTransition() { }

    public OrderStateTransition(Guid orderId, OrderStatus? fromStatus, OrderStatus toStatus, Guid actorUserId, string? reason)
    {
        OrderId = orderId;
        FromStatus = fromStatus;
        ToStatus = toStatus;
        ActorUserId = actorUserId;
        Reason = reason;
    }
}

public class LedgerEntry : BaseEntity
{
    public Guid OrderId { get; private set; }
    public LedgerEntryType EntryType { get; private set; }
    public decimal Amount { get; private set; }
    public string CurrencyCode { get; private set; } = "BRL";
    public string Description { get; private set; } = string.Empty;

    public Order Order { get; private set; } = null!;

    private LedgerEntry() { }

    public LedgerEntry(Guid orderId, LedgerEntryType entryType, decimal amount, string currencyCode, string description)
    {
        OrderId = orderId;
        EntryType = entryType;
        Amount = decimal.Round(amount, 2, MidpointRounding.ToEven);
        CurrencyCode = currencyCode.ToUpperInvariant();
        Description = description;
    }
}
