using YourFood.Domain.Entities;

namespace YourFood.Domain.Repositories;

public interface IRepository<T> where T : BaseEntity
{
    Task<T?> GetByIdAsync(Guid id, CancellationToken ct = default);
    Task<IReadOnlyList<T>> GetAllAsync(CancellationToken ct = default);
    Task AddAsync(T entity, CancellationToken ct = default);
    void Update(T entity);
    void Remove(T entity);
}

public interface IUserRepository : IRepository<User>
{
    Task<User?> GetByEmailAsync(string email, CancellationToken ct = default);
    Task<User?> GetByOAuthAsync(string provider, string subject, CancellationToken ct = default);
    Task<RefreshToken?> GetRefreshTokenByHashAsync(string tokenHash, CancellationToken ct = default);
    Task AddRefreshTokenAsync(RefreshToken token, CancellationToken ct = default);
    Task<OAuthAuthorizationCode?> GetAuthorizationCodeAsync(string code, CancellationToken ct = default);
    Task AddAuthorizationCodeAsync(OAuthAuthorizationCode authCode, CancellationToken ct = default);
}

public interface IStoreRepository : IRepository<Store>
{
    Task<IReadOnlyList<Store>> GetAllWithMenuAsync(string? search, string? category, CancellationToken ct = default);
    Task<Store?> GetByIdWithMenuAsync(Guid storeId, CancellationToken ct = default);
    Task<IReadOnlyList<Store>> GetByOwnerIdAsync(Guid ownerId, CancellationToken ct = default);
    Task<MenuItem?> GetMenuItemByIdAsync(Guid menuItemId, CancellationToken ct = default);
    Task AddMenuItemAsync(MenuItem item, CancellationToken ct = default);
}

public interface IOrderRepository : IRepository<Order>
{
    Task<Order?> GetByIdDetailedAsync(Guid orderId, CancellationToken ct = default);
    Task<IReadOnlyList<Order>> GetByCustomerIdAsync(Guid customerId, CancellationToken ct = default);
    Task<IReadOnlyList<Order>> GetByStoreIdAsync(Guid storeId, CancellationToken ct = default);
    Task<IReadOnlyList<Order>> GetByOwnerIdAsync(Guid ownerId, CancellationToken ct = default);
}

public interface IReviewRepository : IRepository<Review>
{
    Task<Review?> GetByOrderIdAsync(Guid orderId, CancellationToken ct = default);
    Task<Review?> GetByIdDetailedAsync(Guid reviewId, CancellationToken ct = default);
    Task<IReadOnlyList<Review>> GetAllDetailedAsync(Guid? storeId, bool? onlyPendingInference, bool? onlyFlagged, CancellationToken ct = default);
}

public interface IPipelineJobRepository : IRepository<PipelineJob>
{
    Task<IReadOnlyList<PipelineJob>> GetRecentJobsAsync(int limit, CancellationToken ct = default);
}

public interface IAuditLogRepository : IRepository<AuditLog>
{
    Task<IReadOnlyList<AuditLog>> GetRecentAsync(int limit, CancellationToken ct = default);
}

public interface IIdempotencyRepository
{
    Task<IdempotencyRecord?> GetByKeyAsync(string key, string requestPath, CancellationToken ct = default);
    Task AddAsync(IdempotencyRecord record, CancellationToken ct = default);
}

public interface IUnitOfWork
{
    Task<int> SaveChangesAsync(CancellationToken ct = default);
}
