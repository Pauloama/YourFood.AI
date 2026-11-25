using YourFood.Domain.Exceptions;

namespace YourFood.Domain.Entities;

public class Store : BaseEntity
{
    public Guid OwnerId { get; private set; }
    public string Name { get; private set; } = string.Empty;
    public string Category { get; private set; } = string.Empty;
    public string Description { get; private set; } = string.Empty;
    public string Address { get; private set; } = string.Empty;
    public decimal DeliveryFee { get; private set; }
    public int EstimatedDeliveryMinutes { get; private set; }
    public bool IsOpen { get; private set; } = true;

    public User Owner { get; private set; } = null!;
    public ICollection<MenuItem> MenuItems { get; private set; } = new List<MenuItem>();
    public ICollection<Order> Orders { get; private set; } = new List<Order>();

    private Store() { }

    public Store(Guid ownerId, string name, string category, string description, string address, decimal deliveryFee, int estimatedDeliveryMinutes)
    {
        if (deliveryFee < 0)
            throw new DomainException("Delivery fee cannot be negative.", "INVALID_DELIVERY_FEE");

        OwnerId = ownerId;
        Name = name.Trim();
        Category = category.Trim();
        Description = description.Trim();
        Address = address.Trim();
        DeliveryFee = decimal.Round(deliveryFee, 2, MidpointRounding.ToEven);
        EstimatedDeliveryMinutes = Math.Max(10, estimatedDeliveryMinutes);
    }

    public void UpdateDetails(string name, string category, string description, string address, decimal deliveryFee, int estimatedDeliveryMinutes, bool isOpen)
    {
        if (deliveryFee < 0)
            throw new DomainException("Delivery fee cannot be negative.", "INVALID_DELIVERY_FEE");

        Name = name.Trim();
        Category = category.Trim();
        Description = description.Trim();
        Address = address.Trim();
        DeliveryFee = decimal.Round(deliveryFee, 2, MidpointRounding.ToEven);
        EstimatedDeliveryMinutes = Math.Max(10, estimatedDeliveryMinutes);
        IsOpen = isOpen;
        Touch();
    }
}

public class MenuItem : BaseEntity
{
    public Guid StoreId { get; private set; }
    public string Name { get; private set; } = string.Empty;
    public string Description { get; private set; } = string.Empty;
    public string Category { get; private set; } = string.Empty;
    public decimal Price { get; private set; }
    public string CurrencyCode { get; private set; } = "BRL";
    public bool IsAvailable { get; private set; } = true;

    public Store Store { get; private set; } = null!;

    private MenuItem() { }

    public MenuItem(Guid storeId, string name, string description, string category, decimal price, string currencyCode = "BRL")
    {
        if (price <= 0)
            throw new DomainException("Item price must be greater than zero.", "INVALID_PRICE");

        StoreId = storeId;
        Name = name.Trim();
        Description = description.Trim();
        Category = category.Trim();
        Price = decimal.Round(price, 2, MidpointRounding.ToEven);
        CurrencyCode = currencyCode.ToUpperInvariant();
    }

    public void Update(string name, string description, string category, decimal price, bool isAvailable)
    {
        if (price <= 0)
            throw new DomainException("Item price must be greater than zero.", "INVALID_PRICE");

        Name = name.Trim();
        Description = description.Trim();
        Category = category.Trim();
        Price = decimal.Round(price, 2, MidpointRounding.ToEven);
        IsAvailable = isAvailable;
        Touch();
    }
}
