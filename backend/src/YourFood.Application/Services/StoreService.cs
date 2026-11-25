using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;
using YourFood.Domain.Repositories;

namespace YourFood.Application.Services;

public interface IStoreService
{
    Task<IReadOnlyList<StoreDto>> ListStoresAsync(string? search, string? category, CancellationToken ct = default);
    Task<StoreDto> GetStoreAsync(Guid storeId, CancellationToken ct = default);
    Task<IReadOnlyList<StoreDto>> GetOwnerStoresAsync(Guid ownerId, CancellationToken ct = default);
    Task<StoreDto> CreateStoreAsync(Guid ownerId, CreateStoreRequest request, CancellationToken ct = default);
    Task<StoreDto> UpdateStoreAsync(Guid actorId, UserRole actorRole, Guid storeId, UpdateStoreRequest request, CancellationToken ct = default);
    Task<MenuItemDto> AddMenuItemAsync(Guid actorId, UserRole actorRole, Guid storeId, CreateMenuItemRequest request, CancellationToken ct = default);
    Task<MenuItemDto> UpdateMenuItemAsync(Guid actorId, UserRole actorRole, Guid menuItemId, UpdateMenuItemRequest request, CancellationToken ct = default);
}

public class StoreService : IStoreService
{
    private readonly IStoreRepository _stores;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IAuditTrailService _audit;

    public StoreService(IStoreRepository stores, IUnitOfWork unitOfWork, IAuditTrailService audit)
    {
        _stores = stores;
        _unitOfWork = unitOfWork;
        _audit = audit;
    }

    public async Task<IReadOnlyList<StoreDto>> ListStoresAsync(string? search, string? category, CancellationToken ct = default)
    {
        var stores = await _stores.GetAllWithMenuAsync(search, category, ct);
        return stores.Select(MapStore).ToList();
    }

    public async Task<StoreDto> GetStoreAsync(Guid storeId, CancellationToken ct = default)
    {
        var store = await _stores.GetByIdWithMenuAsync(storeId, ct)
            ?? throw new NotFoundException(nameof(Store), storeId);
        return MapStore(store);
    }

    public async Task<IReadOnlyList<StoreDto>> GetOwnerStoresAsync(Guid ownerId, CancellationToken ct = default)
    {
        var stores = await _stores.GetByOwnerIdAsync(ownerId, ct);
        return stores.Select(MapStore).ToList();
    }

    public async Task<StoreDto> CreateStoreAsync(Guid ownerId, CreateStoreRequest request, CancellationToken ct = default)
    {
        var store = new Store(
            ownerId,
            request.Name,
            request.Category,
            request.Description,
            request.Address,
            request.DeliveryFee,
            request.EstimatedDeliveryMinutes);

        await _stores.AddAsync(store, ct);
        await _audit.RecordAsync(ownerId, "STORE_CREATED", nameof(Store), store.Id.ToString(), request, $"Store '{store.Name}' created", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return MapStore(store);
    }

    public async Task<StoreDto> UpdateStoreAsync(Guid actorId, UserRole actorRole, Guid storeId, UpdateStoreRequest request, CancellationToken ct = default)
    {
        var store = await _stores.GetByIdWithMenuAsync(storeId, ct)
            ?? throw new NotFoundException(nameof(Store), storeId);

        EnsureOwnerOrAdmin(store.OwnerId, actorId, actorRole);

        store.UpdateDetails(
            request.Name,
            request.Category,
            request.Description,
            request.Address,
            request.DeliveryFee,
            request.EstimatedDeliveryMinutes,
            request.IsOpen);

        _stores.Update(store);
        await _audit.RecordAsync(actorId, "STORE_UPDATED", nameof(Store), store.Id.ToString(), request, $"Store '{store.Name}' updated", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return MapStore(store);
    }

    public async Task<MenuItemDto> AddMenuItemAsync(Guid actorId, UserRole actorRole, Guid storeId, CreateMenuItemRequest request, CancellationToken ct = default)
    {
        var store = await _stores.GetByIdWithMenuAsync(storeId, ct)
            ?? throw new NotFoundException(nameof(Store), storeId);

        EnsureOwnerOrAdmin(store.OwnerId, actorId, actorRole);

        var item = new MenuItem(storeId, request.Name, request.Description, request.Category, request.Price);
        await _stores.AddMenuItemAsync(item, ct);
        await _audit.RecordAsync(actorId, "MENU_ITEM_CREATED", nameof(MenuItem), item.Id.ToString(), request, $"Menu item '{item.Name}' added to '{store.Name}'", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return MapMenuItem(item);
    }

    public async Task<MenuItemDto> UpdateMenuItemAsync(Guid actorId, UserRole actorRole, Guid menuItemId, UpdateMenuItemRequest request, CancellationToken ct = default)
    {
        var item = await _stores.GetMenuItemByIdAsync(menuItemId, ct)
            ?? throw new NotFoundException(nameof(MenuItem), menuItemId);

        var store = await _stores.GetByIdAsync(item.StoreId, ct)
            ?? throw new NotFoundException(nameof(Store), item.StoreId);

        EnsureOwnerOrAdmin(store.OwnerId, actorId, actorRole);

        item.Update(request.Name, request.Description, request.Category, request.Price, request.IsAvailable);
        await _audit.RecordAsync(actorId, "MENU_ITEM_UPDATED", nameof(MenuItem), item.Id.ToString(), request, $"Menu item '{item.Name}' updated", ct);
        await _unitOfWork.SaveChangesAsync(ct);

        return MapMenuItem(item);
    }

    private static void EnsureOwnerOrAdmin(Guid ownerId, Guid actorId, UserRole actorRole)
    {
        if (actorRole != UserRole.Admin && ownerId != actorId)
            throw new ForbiddenException("Only the store owner or an administrator can modify this store.");
    }

    private static StoreDto MapStore(Store store) =>
        new(
            store.Id,
            store.OwnerId,
            store.Name,
            store.Category,
            store.Description,
            store.Address,
            store.DeliveryFee,
            store.EstimatedDeliveryMinutes,
            store.IsOpen,
            store.MenuItems.Select(MapMenuItem).ToList());

    private static MenuItemDto MapMenuItem(MenuItem item) =>
        new(item.Id, item.StoreId, item.Name, item.Description, item.Category, item.Price, item.CurrencyCode, item.IsAvailable);
}
