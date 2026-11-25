using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using YourFood.Application.Interfaces;
using YourFood.Application.Services;
using YourFood.Domain.Repositories;
using YourFood.Infrastructure.External;
using YourFood.Infrastructure.Persistence;
using YourFood.Infrastructure.Repositories;
using YourFood.Infrastructure.Security;

namespace YourFood.Infrastructure;

public static class DependencyInjection
{
    public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration configuration)
    {
        services.Configure<JwtSettings>(configuration.GetSection("Jwt"));
        services.Configure<AbsaServiceSettings>(configuration.GetSection("AbsaService"));

        var connectionString = configuration.GetConnectionString("DefaultConnection")
            ?? "Host=localhost;Port=5432;Database=yourfood;Username=postgres;Password=postgres";

        services.AddDbContext<YourFoodDbContext>(options =>
            options.UseNpgsql(connectionString));

        services.AddScoped<IUserRepository, UserRepository>();
        services.AddScoped<IStoreRepository, StoreRepository>();
        services.AddScoped<IOrderRepository, OrderRepository>();
        services.AddScoped<IReviewRepository, ReviewRepository>();
        services.AddScoped<IPipelineJobRepository, PipelineJobRepository>();
        services.AddScoped<IAuditLogRepository, AuditLogRepository>();
        services.AddScoped<IIdempotencyRepository, IdempotencyRepository>();
        services.AddScoped<IUnitOfWork, UnitOfWork>();

        services.AddScoped<IPasswordHasher, BCryptPasswordHasher>();
        services.AddScoped<IJwtTokenService, JwtTokenService>();
        services.AddScoped<IAuditTrailService, AuditTrailService>();
        services.AddScoped<IPipelineProcessRunner, PipelineProcessRunner>();

        services.AddHttpClient<IAbsaInferenceClient, AbsaInferenceClient>();

        services.AddScoped<IAuthService, AuthService>();
        services.AddScoped<IStoreService, StoreService>();
        services.AddScoped<IOrderService, OrderService>();
        services.AddScoped<IReviewService, ReviewService>();
        services.AddScoped<IPipelineOrchestrationService, PipelineOrchestrationService>();

        return services;
    }
}
