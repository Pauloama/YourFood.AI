using Microsoft.EntityFrameworkCore;
using YourFood.Domain.Entities;

namespace YourFood.Infrastructure.Persistence;

public class YourFoodDbContext : DbContext
{
    public YourFoodDbContext(DbContextOptions<YourFoodDbContext> options) : base(options)
    {
    }

    public DbSet<User> Users => Set<User>();
    public DbSet<RefreshToken> RefreshTokens => Set<RefreshToken>();
    public DbSet<OAuthAuthorizationCode> OAuthAuthorizationCodes => Set<OAuthAuthorizationCode>();
    public DbSet<Store> Stores => Set<Store>();
    public DbSet<MenuItem> MenuItems => Set<MenuItem>();
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<OrderItem> OrderItems => Set<OrderItem>();
    public DbSet<OrderStateTransition> OrderStateTransitions => Set<OrderStateTransition>();
    public DbSet<LedgerEntry> LedgerEntries => Set<LedgerEntry>();
    public DbSet<Review> Reviews => Set<Review>();
    public DbSet<ReviewAnnotation> ReviewAnnotations => Set<ReviewAnnotation>();
    public DbSet<ReviewPrediction> ReviewPredictions => Set<ReviewPrediction>();
    public DbSet<PipelineJob> PipelineJobs => Set<PipelineJob>();
    public DbSet<AuditLog> AuditLogs => Set<AuditLog>();
    public DbSet<IdempotencyRecord> IdempotencyRecords => Set<IdempotencyRecord>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<User>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasIndex(x => x.Email).IsUnique();
            e.HasIndex(x => new { x.OAuthProvider, x.OAuthSubject });
            e.Property(x => x.FullName).HasMaxLength(160).IsRequired();
            e.Property(x => x.Email).HasMaxLength(200).IsRequired();
            e.Property(x => x.PasswordHash).HasMaxLength(256).IsRequired();
        });

        modelBuilder.Entity<RefreshToken>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasIndex(x => x.TokenHash).IsUnique();
            e.HasOne(x => x.User).WithMany(u => u.RefreshTokens).HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<OAuthAuthorizationCode>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasIndex(x => x.Code).IsUnique();
        });

        modelBuilder.Entity<Store>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Name).HasMaxLength(160).IsRequired();
            e.Property(x => x.Category).HasMaxLength(80).IsRequired();
            e.Property(x => x.DeliveryFee).HasPrecision(18, 2);
            e.HasOne(x => x.Owner).WithMany(u => u.Stores).HasForeignKey(x => x.OwnerId).OnDelete(DeleteBehavior.Restrict);
        });

        modelBuilder.Entity<MenuItem>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Name).HasMaxLength(160).IsRequired();
            e.Property(x => x.Price).HasPrecision(18, 2);
            e.Property(x => x.CurrencyCode).HasMaxLength(8).IsRequired();
            e.HasOne(x => x.Store).WithMany(s => s.MenuItems).HasForeignKey(x => x.StoreId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<Order>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.SubtotalAmount).HasPrecision(18, 2);
            e.Property(x => x.DeliveryFeeAmount).HasPrecision(18, 2);
            e.Property(x => x.TotalAmount).HasPrecision(18, 2);
            e.Property(x => x.CurrencyCode).HasMaxLength(8).IsRequired();
            e.HasOne(x => x.Customer).WithMany(u => u.Orders).HasForeignKey(x => x.CustomerId).OnDelete(DeleteBehavior.Restrict);
            e.HasOne(x => x.Store).WithMany(s => s.Orders).HasForeignKey(x => x.StoreId).OnDelete(DeleteBehavior.Restrict);
        });

        modelBuilder.Entity<OrderItem>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).ValueGeneratedNever();
            e.Property(x => x.UnitPriceSnapshot).HasPrecision(18, 2);
            e.Property(x => x.LineTotal).HasPrecision(18, 2);
            e.HasOne(x => x.Order).WithMany(o => o.Items).HasForeignKey(x => x.OrderId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<OrderStateTransition>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).ValueGeneratedNever();
            e.HasOne(x => x.Order).WithMany(o => o.StateHistory).HasForeignKey(x => x.OrderId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<LedgerEntry>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).ValueGeneratedNever();
            e.Property(x => x.Amount).HasPrecision(18, 2);
            e.Property(x => x.CurrencyCode).HasMaxLength(8).IsRequired();
            e.HasOne(x => x.Order).WithMany(o => o.LedgerEntries).HasForeignKey(x => x.OrderId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<Review>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasIndex(x => x.OrderId).IsUnique();
            e.Property(x => x.Text).HasMaxLength(2048).IsRequired();
            e.HasOne(x => x.Order).WithOne(o => o.Review).HasForeignKey<Review>(x => x.OrderId).OnDelete(DeleteBehavior.Cascade);
            e.HasOne(x => x.Customer).WithMany().HasForeignKey(x => x.CustomerId).OnDelete(DeleteBehavior.Restrict);
            e.HasOne(x => x.Store).WithMany().HasForeignKey(x => x.StoreId).OnDelete(DeleteBehavior.Restrict);
        });

        modelBuilder.Entity<ReviewAnnotation>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).ValueGeneratedNever();
            e.Property(x => x.Aspect).HasMaxLength(64).IsRequired();
            e.Property(x => x.Entity).HasMaxLength(32).IsRequired();
            e.Property(x => x.Sentiment).HasMaxLength(32).IsRequired();
            e.HasOne(x => x.Review).WithMany(r => r.Annotations).HasForeignKey(x => x.ReviewId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<ReviewPrediction>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).ValueGeneratedNever();
            e.HasOne(x => x.Review).WithMany(r => r.Predictions).HasForeignKey(x => x.ReviewId).OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<PipelineJob>(e =>
        {
            e.HasKey(x => x.Id);
        });

        modelBuilder.Entity<AuditLog>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasIndex(x => x.CreatedAtUtc);
            e.HasIndex(x => x.CorrelationId);
        });

        modelBuilder.Entity<IdempotencyRecord>(e =>
        {
            e.HasKey(x => x.Id);
            e.HasIndex(x => new { x.Key, x.RequestPath }).IsUnique();
        });
    }
}
