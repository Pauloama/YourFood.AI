using Microsoft.EntityFrameworkCore;
using YourFood.Application.Interfaces;
using YourFood.Domain.Entities;
using YourFood.Domain.Enums;

namespace YourFood.Infrastructure.Persistence;

public static class DatabaseSeeder
{
    public static async Task SeedAsync(YourFoodDbContext context, IPasswordHasher passwordHasher, CancellationToken ct = default)
    {
        await context.Database.EnsureCreatedAsync(ct);

        if (await context.Users.AnyAsync(ct))
            return;

        var admin = new User("Admin MLOps YourFood", "admin@yourfood.ai", passwordHasher.Hash("Admin@123"), UserRole.Admin);
        var merchant = new User("Carlos Chef", "merchant@yourfood.ai", passwordHasher.Hash("Merchant@123"), UserRole.StoreOwner);
        var customer = new User("Ana Cliente", "customer@yourfood.ai", passwordHasher.Hash("Customer@123"), UserRole.Customer);

        await context.Users.AddRangeAsync([admin, merchant, customer], ct);

        var burgerHouse = new Store(
            merchant.Id,
            "Brasa & Blend Burger",
            "Hamburgueria",
            "Hambúrgueres artesanais grelhados no fogo com pães brioche frescos.",
            "Av. Paulista, 1420 - São Paulo, SP",
            7.90m,
            35);

        var pizzeria = new Store(
            merchant.Id,
            "Forno D'Oro Pizzaria",
            "Pizzaria",
            "Massas de fermentação natural 48h assadas em forno a lenha.",
            "Rua Augusta, 890 - São Paulo, SP",
            9.50m,
            45);

        var sushiLab = new Store(
            merchant.Id,
            "Kuro Sushi Lab",
            "Japonesa",
            "Combinados frescos, sashimis selecionados e embalagem térmica lacrada.",
            "Alameda Santos, 512 - São Paulo, SP",
            12.00m,
            40);

        await context.Stores.AddRangeAsync([burgerHouse, pizzeria, sushiLab], ct);

        var b1 = new MenuItem(burgerHouse.Id, "Smash Duplo Cheddar", "Dois discos de 100g, cheddar cremoso e cebola caramelizada.", "Burgers", 36.90m);
        var b2 = new MenuItem(burgerHouse.Id, "Batata Rústica com Alecrim", "Porção generosa de batatas crocantes com maionese da casa.", "Acompanhamentos", 18.50m);
        var b3 = new MenuItem(burgerHouse.Id, "Refrigerante Lata 350ml", "Coca-Cola ou Guaraná bem gelado.", "Bebidas", 7.50m);

        var p1 = new MenuItem(pizzeria.Id, "Pizza Margherita DOP", "Molho de tomate italiano, mozzarella de búfala e manjericão fresco.", "Pizzas", 64.00m);
        var p2 = new MenuItem(pizzeria.Id, "Pizza Calabresa Artesanal", "Calabresa defumada, cebola roxa e azeitonas pretas.", "Pizzas", 59.90m);

        var s1 = new MenuItem(sushiLab.Id, "Combo Salmão 24 peças", "Sashimis, niguiris e uramakis de salmão fresco.", "Combinados", 89.90m);
        var s2 = new MenuItem(sushiLab.Id, "Hot Roll Crocante 10 un", "Salmão com cream cheese empanado e molho tarê.", "Quentes", 34.00m);

        await context.MenuItems.AddRangeAsync([b1, b2, b3, p1, p2, s1, s2], ct);

        var deliveredOrder1 = new Order(
            customer.Id,
            burgerHouse.Id,
            "Rua Oscar Freire, 320 - Apto 42",
            burgerHouse.DeliveryFee,
            "Sem picles por favor",
            [new OrderItem(b1.Id, b1.Name, b1.Price, 1), new OrderItem(b2.Id, b2.Name, b2.Price, 1)]);

        deliveredOrder1.TransitionTo(OrderStatus.Confirmed, customer.Id, "Payment authorized");
        deliveredOrder1.TransitionTo(OrderStatus.Preparing, merchant.Id, "Kitchen started");
        deliveredOrder1.TransitionTo(OrderStatus.ReadyForPickup, merchant.Id, "Order sealed");
        deliveredOrder1.TransitionTo(OrderStatus.OutForDelivery, merchant.Id, "Courier dispatched");
        deliveredOrder1.TransitionTo(OrderStatus.Delivered, merchant.Id, "Delivered to customer");

        var deliveredOrder2 = new Order(
            customer.Id,
            pizzeria.Id,
            "Rua Oscar Freire, 320 - Apto 42",
            pizzeria.DeliveryFee,
            null,
            [new OrderItem(p1.Id, p1.Name, p1.Price, 1)]);

        deliveredOrder2.TransitionTo(OrderStatus.Confirmed, customer.Id, "Payment authorized");
        deliveredOrder2.TransitionTo(OrderStatus.Preparing, merchant.Id, "Oven ready");
        deliveredOrder2.TransitionTo(OrderStatus.ReadyForPickup, merchant.Id, "Boxed");
        deliveredOrder2.TransitionTo(OrderStatus.OutForDelivery, merchant.Id, "On the way");
        deliveredOrder2.TransitionTo(OrderStatus.Delivered, merchant.Id, "Delivered");

        await context.Orders.AddRangeAsync([deliveredOrder1, deliveredOrder2], ct);

        var review1 = new Review(
            deliveredOrder1.Id,
            customer.Id,
            burgerHouse.Id,
            "O hambúrguer estava delicioso e bem temperado, mas chegou um pouco frio e a entrega demorou.",
            4);

        review1.SetAnnotations([
            new ReviewAnnotation("sabor", "positivo", "delicioso e bem temperado"),
            new ReviewAnnotation("temperatura", "negativo", "chegou um pouco frio"),
            new ReviewAnnotation("tempo_entrega", "negativo", "a entrega demorou")
        ]);

        var review2 = new Review(
            deliveredOrder2.Id,
            customer.Id,
            pizzeria.Id,
            "Pizza quentinha, massa crocante no ponto certo e embalagem super protegida!",
            5);

        review2.SetAnnotations([
            new ReviewAnnotation("temperatura", "positivo", "Pizza quentinha"),
            new ReviewAnnotation("preparo", "positivo", "massa crocante no ponto certo"),
            new ReviewAnnotation("embalagem", "positivo", "embalagem super protegida")
        ]);

        await context.Reviews.AddRangeAsync([review1, review2], ct);
        await context.SaveChangesAsync(ct);
    }
}
