using Microsoft.EntityFrameworkCore;
using YourFood.Application.DTOs;
using YourFood.Application.Interfaces;
using YourFood.Application.Services;
using YourFood.Domain.Constants;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;
using YourFood.Domain.Exceptions;
using YourFood.Infrastructure.Persistence;
using YourFood.Infrastructure.Repositories;
using YourFood.Infrastructure.Security;
using Xunit;

namespace YourFood.Tests;

public class DomainAndApplicationTests
{
    [Fact]
    public void OrderStateMachine_EnforcesValidTransitionsAndFintechLedger()
    {
        var customerId = Guid.NewGuid();
        var merchantId = Guid.NewGuid();
        var storeId = Guid.NewGuid();
        var item = new OrderItem(Guid.NewGuid(), "Smash Duplo", 35.50m, 2);

        var order = new Order(customerId, storeId, "Av. Paulista, 100", 8.00m, null, [item]);

        Assert.Equal(OrderStatus.PendingPayment, order.Status);
        Assert.Equal(71.00m, order.SubtotalAmount);
        Assert.Equal(79.00m, order.TotalAmount);
        Assert.Single(order.LedgerEntries);

        Assert.Throws<DomainException>(() => order.TransitionTo(OrderStatus.Delivered, merchantId));

        order.TransitionTo(OrderStatus.Confirmed, customerId);
        order.TransitionTo(OrderStatus.Preparing, merchantId);
        order.TransitionTo(OrderStatus.ReadyForPickup, merchantId);
        order.TransitionTo(OrderStatus.OutForDelivery, merchantId);
        order.TransitionTo(OrderStatus.Delivered, merchantId);

        Assert.Equal(OrderStatus.Delivered, order.Status);
        Assert.Equal(6, order.StateHistory.Count);
        Assert.Contains(order.LedgerEntries, e => e.EntryType == LedgerEntryType.MerchantSettlement && e.Amount == 71.00m);
    }

    [Fact]
    public void OrderCancellation_GeneratesRefundLedgerEntry()
    {
        var customerId = Guid.NewGuid();
        var item = new OrderItem(Guid.NewGuid(), "Pizza", 50.00m, 1);
        var order = new Order(customerId, Guid.NewGuid(), "Rua A, 10", 10.00m, null, [item]);

        order.TransitionTo(OrderStatus.Cancelled, customerId, "Customer cancelled");

        Assert.Equal(OrderStatus.Cancelled, order.Status);
        Assert.Contains(order.LedgerEntries, e => e.EntryType == LedgerEntryType.OrderRefund && e.Amount == -60.00m);
    }

    [Fact]
    public void ReviewAnnotations_DetectsSentimentConflictsAndValidatesTaxonomy()
    {
        var review = new Review(Guid.NewGuid(), Guid.NewGuid(), Guid.NewGuid(), "Sabor bom no inicio mas ruim depois.", 3);

        review.SetAnnotations([
            new ReviewAnnotation("sabor", "positivo"),
            new ReviewAnnotation("sabor", "negativo")
        ]);

        Assert.True(review.RequiresReview);
        Assert.Throws<DomainException>(() => new ReviewAnnotation("aspecto_invalido", "positivo"));
        Assert.Equal("produto", AbsaTaxonomy.ResolveEntity("temperatura"));
        Assert.Equal("loja", AbsaTaxonomy.ResolveEntity("embalagem"));
        Assert.Equal("entrega", AbsaTaxonomy.ResolveEntity("tempo_entrega"));
    }

    [Fact]
    public async Task ExportDataset_GeneratesCanonicalJsonlCompatibleWithBertimbauPipeline()
    {
        var options = new DbContextOptionsBuilder<YourFoodDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var db = new YourFoodDbContext(options);
        var hasher = new BCryptPasswordHasher();
        await DatabaseSeeder.SeedAsync(db, hasher);

        var correlation = new StaticCorrelationContext();
        var audit = new AuditTrailService(new AuditLogRepository(db), correlation);
        var service = new PipelineOrchestrationService(
            new ReviewRepository(db),
            new StoreRepository(db),
            new OrderRepository(db),
            new PipelineJobRepository(db),
            new AuditLogRepository(db),
            new UnitOfWork(db),
            new FakePipelineRunner(),
            audit);

        var admin = await db.Users.FirstAsync(u => u.Role == UserRole.Admin);
        var export = await service.ExportDatasetAsync(admin.Id, new ExportDatasetRequest("jsonl", true, true, false));

        Assert.Equal(2, export.TotalReviews);
        Assert.Equal(6, export.TotalRows);
        Assert.Contains("\"aspect\":\"sabor\"", export.Content);
        Assert.Contains("\"sentiment\":\"positivo\"", export.Content);
    }

    [Fact]
    public async Task OrderService_PersistsStateTransitionAndChildRecordsCleanly()
    {
        var options = new DbContextOptionsBuilder<YourFoodDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var db = new YourFoodDbContext(options);
        var hasher = new BCryptPasswordHasher();
        await DatabaseSeeder.SeedAsync(db, hasher);

        var customer = await db.Users.FirstAsync(u => u.Role == UserRole.Customer);
        var merchant = await db.Users.FirstAsync(u => u.Role == UserRole.StoreOwner);
        var store = await db.Stores.Include(s => s.MenuItems).FirstAsync();
        var item = store.MenuItems.First();

        var correlation = new StaticCorrelationContext();
        var audit = new AuditTrailService(new AuditLogRepository(db), correlation);
        var orderService = new OrderService(new OrderRepository(db), new StoreRepository(db), new UnitOfWork(db), audit);

        var created = await orderService.CreateOrderAsync(customer.Id, new CreateOrderRequest(store.Id, "Rua Teste 123", null, [new OrderItemInput(item.Id, 1)]));
        var confirmed = await orderService.TransitionOrderAsync(customer.Id, UserRole.Customer, created.Id, new TransitionOrderStatusRequest(OrderStatus.Confirmed, "Paid"));
        var preparing = await orderService.TransitionOrderAsync(merchant.Id, UserRole.StoreOwner, created.Id, new TransitionOrderStatusRequest(OrderStatus.Preparing, "Kitchen"));

        Assert.Equal("Confirmed", confirmed.Status);
        Assert.Equal("Preparing", preparing.Status);
        Assert.Equal(3, preparing.StateHistory.Count);
    }

    private sealed class StaticCorrelationContext : ICorrelationContext
    {
        public string CorrelationId => "test-correlation-id";
    }

    private sealed class FakePipelineRunner : IPipelineProcessRunner
    {
        public string BuildCommandPreview(PipelineStepType step, string? datasetFileName, int seed) => "preview";
        public string SaveDatasetFile(string fileName, string content) => fileName;
        public Task<(int ExitCode, string OutputLog, string ErrorLog, string? ReportJson)> ExecuteStepAsync(PipelineStepType step, string? datasetFileName, int seed, CancellationToken ct = default) =>
            Task.FromResult((0, "ok", string.Empty, (string?)null));
    }
}
