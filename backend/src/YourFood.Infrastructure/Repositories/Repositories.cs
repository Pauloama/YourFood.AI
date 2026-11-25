using Microsoft.EntityFrameworkCore;
using YourFood.Domain.Entities;
using YourFood.Domain.Repositories;

namespace YourFood.Infrastructure.Repositories;

public class Repository<T> : IRepository<T> where T : BaseEntity
{
    protected readonly Persistence.YourFoodDbContext Context;
    protected readonly DbSet<T> DbSet;

    public Repository(Persistence.YourFoodDbContext context)
    {
        Context = context;
        DbSet = context.Set<T>();
    }

    public virtual async Task<T?> GetByIdAsync(Guid id, CancellationToken ct = default) =>
        await DbSet.FirstOrDefaultAsync(x => x.Id == id, ct);

    public virtual async Task<IReadOnlyList<T>> GetAllAsync(CancellationToken ct = default) =>
        await DbSet.OrderByDescending(x => x.CreatedAtUtc).ToListAsync(ct);

    public virtual async Task AddAsync(T entity, CancellationToken ct = default) =>
        await DbSet.AddAsync(entity, ct);

    public virtual void Update(T entity)
    {
        if (Context.Entry(entity).State == EntityState.Detached)
            DbSet.Update(entity);
    }

    public virtual void Remove(T entity) => DbSet.Remove(entity);
}

public class UserRepository : Repository<User>, IUserRepository
{
    public UserRepository(Persistence.YourFoodDbContext context) : base(context) { }

    public async Task<User?> GetByEmailAsync(string email, CancellationToken ct = default) =>
        await DbSet.FirstOrDefaultAsync(u => u.Email == email, ct);

    public async Task<User?> GetByOAuthAsync(string provider, string subject, CancellationToken ct = default) =>
        await DbSet.FirstOrDefaultAsync(u => u.OAuthProvider == provider && u.OAuthSubject == subject, ct);

    public async Task<RefreshToken?> GetRefreshTokenByHashAsync(string tokenHash, CancellationToken ct = default) =>
        await Context.RefreshTokens.FirstOrDefaultAsync(r => r.TokenHash == tokenHash, ct);

    public async Task AddRefreshTokenAsync(RefreshToken token, CancellationToken ct = default) =>
        await Context.RefreshTokens.AddAsync(token, ct);

    public async Task<OAuthAuthorizationCode?> GetAuthorizationCodeAsync(string code, CancellationToken ct = default) =>
        await Context.OAuthAuthorizationCodes.FirstOrDefaultAsync(c => c.Code == code, ct);

    public async Task AddAuthorizationCodeAsync(OAuthAuthorizationCode authCode, CancellationToken ct = default) =>
        await Context.OAuthAuthorizationCodes.AddAsync(authCode, ct);
}

public class StoreRepository : Repository<Store>, IStoreRepository
{
    public StoreRepository(Persistence.YourFoodDbContext context) : base(context) { }

    public async Task<IReadOnlyList<Store>> GetAllWithMenuAsync(string? search, string? category, CancellationToken ct = default)
    {
        var query = DbSet.Include(s => s.MenuItems).AsQueryable();

        if (!string.IsNullOrWhiteSpace(category))
        {
            var cat = category.Trim().ToLowerInvariant();
            query = query.Where(s => s.Category.ToLower() == cat);
        }

        if (!string.IsNullOrWhiteSpace(search))
        {
            var term = search.Trim().ToLowerInvariant();
            query = query.Where(s =>
                s.Name.ToLower().Contains(term) ||
                s.Description.ToLower().Contains(term) ||
                s.MenuItems.Any(m => m.Name.ToLower().Contains(term)));
        }

        return await query.OrderBy(s => s.Name).ToListAsync(ct);
    }

    public async Task<Store?> GetByIdWithMenuAsync(Guid storeId, CancellationToken ct = default) =>
        await DbSet.Include(s => s.MenuItems).FirstOrDefaultAsync(s => s.Id == storeId, ct);

    public async Task<IReadOnlyList<Store>> GetByOwnerIdAsync(Guid ownerId, CancellationToken ct = default) =>
        await DbSet.Include(s => s.MenuItems).Where(s => s.OwnerId == ownerId).OrderBy(s => s.Name).ToListAsync(ct);

    public async Task<MenuItem?> GetMenuItemByIdAsync(Guid menuItemId, CancellationToken ct = default) =>
        await Context.MenuItems.FirstOrDefaultAsync(m => m.Id == menuItemId, ct);

    public async Task AddMenuItemAsync(MenuItem item, CancellationToken ct = default) =>
        await Context.MenuItems.AddAsync(item, ct);
}

public class OrderRepository : Repository<Order>, IOrderRepository
{
    public OrderRepository(Persistence.YourFoodDbContext context) : base(context) { }

    private IQueryable<Order> DetailedQuery() =>
        DbSet
            .Include(o => o.Store)
            .Include(o => o.Items)
            .Include(o => o.StateHistory)
            .Include(o => o.LedgerEntries)
            .Include(o => o.Review);

    public async Task<Order?> GetByIdDetailedAsync(Guid orderId, CancellationToken ct = default) =>
        await DetailedQuery().FirstOrDefaultAsync(o => o.Id == orderId, ct);

    public async Task<IReadOnlyList<Order>> GetByCustomerIdAsync(Guid customerId, CancellationToken ct = default) =>
        await DetailedQuery().Where(o => o.CustomerId == customerId).OrderByDescending(o => o.CreatedAtUtc).ToListAsync(ct);

    public async Task<IReadOnlyList<Order>> GetByStoreIdAsync(Guid storeId, CancellationToken ct = default) =>
        await DetailedQuery().Where(o => o.StoreId == storeId).OrderByDescending(o => o.CreatedAtUtc).ToListAsync(ct);

    public async Task<IReadOnlyList<Order>> GetByOwnerIdAsync(Guid ownerId, CancellationToken ct = default) =>
        await DetailedQuery().Where(o => o.Store.OwnerId == ownerId).OrderByDescending(o => o.CreatedAtUtc).ToListAsync(ct);
}

public class ReviewRepository : Repository<Review>, IReviewRepository
{
    public ReviewRepository(Persistence.YourFoodDbContext context) : base(context) { }

    private IQueryable<Review> DetailedQuery() =>
        DbSet
            .Include(r => r.Store)
            .Include(r => r.Annotations)
            .Include(r => r.Predictions);

    public async Task<Review?> GetByOrderIdAsync(Guid orderId, CancellationToken ct = default) =>
        await DetailedQuery().FirstOrDefaultAsync(r => r.OrderId == orderId, ct);

    public async Task<Review?> GetByIdDetailedAsync(Guid reviewId, CancellationToken ct = default) =>
        await DetailedQuery().FirstOrDefaultAsync(r => r.Id == reviewId, ct);

    public async Task<IReadOnlyList<Review>> GetAllDetailedAsync(Guid? storeId, bool? onlyPendingInference, bool? onlyFlagged, CancellationToken ct = default)
    {
        var query = DetailedQuery();

        if (storeId.HasValue)
            query = query.Where(r => r.StoreId == storeId.Value);

        if (onlyPendingInference == true)
            query = query.Where(r => r.LastAnalyzedAtUtc == null);

        if (onlyFlagged == true)
            query = query.Where(r => r.RequiresReview);

        return await query.OrderByDescending(r => r.CreatedAtUtc).ToListAsync(ct);
    }
}

public class PipelineJobRepository : Repository<PipelineJob>, IPipelineJobRepository
{
    public PipelineJobRepository(Persistence.YourFoodDbContext context) : base(context) { }

    public async Task<IReadOnlyList<PipelineJob>> GetRecentJobsAsync(int limit, CancellationToken ct = default) =>
        await DbSet.OrderByDescending(j => j.CreatedAtUtc).Take(limit).ToListAsync(ct);
}

public class AuditLogRepository : Repository<AuditLog>, IAuditLogRepository
{
    public AuditLogRepository(Persistence.YourFoodDbContext context) : base(context) { }

    public async Task<IReadOnlyList<AuditLog>> GetRecentAsync(int limit, CancellationToken ct = default) =>
        await DbSet.OrderByDescending(a => a.CreatedAtUtc).Take(limit).ToListAsync(ct);
}

public class IdempotencyRepository : IIdempotencyRepository
{
    private readonly Persistence.YourFoodDbContext _context;

    public IdempotencyRepository(Persistence.YourFoodDbContext context)
    {
        _context = context;
    }

    public async Task<IdempotencyRecord?> GetByKeyAsync(string key, string requestPath, CancellationToken ct = default) =>
        await _context.IdempotencyRecords.FirstOrDefaultAsync(r => r.Key == key && r.RequestPath == requestPath && r.ExpiresAtUtc > DateTime.UtcNow, ct);

    public async Task AddAsync(IdempotencyRecord record, CancellationToken ct = default) =>
        await _context.IdempotencyRecords.AddAsync(record, ct);
}

public class UnitOfWork : IUnitOfWork
{
    private readonly Persistence.YourFoodDbContext _context;

    public UnitOfWork(Persistence.YourFoodDbContext context)
    {
        _context = context;
    }

    public Task<int> SaveChangesAsync(CancellationToken ct = default) =>
        _context.SaveChangesAsync(ct);
}
