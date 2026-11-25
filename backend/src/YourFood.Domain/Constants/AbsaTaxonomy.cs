namespace YourFood.Domain.Constants;

public static class AbsaTaxonomy
{
    public const string Version = "food-reviews-taxonomy-v1";

    public static readonly IReadOnlyList<string> Aspects =
    [
        "sabor",
        "qualidade",
        "quantidade",
        "temperatura",
        "aparencia",
        "preparo",
        "atendimento",
        "pedido_correto",
        "embalagem",
        "custo_beneficio",
        "tempo_entrega",
        "condicao_entrega"
    ];

    public static readonly IReadOnlyList<string> Sentiments =
    [
        "positivo",
        "negativo",
        "neutro"
    ];

    public static readonly IReadOnlyDictionary<string, string> EntityMapping =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["sabor"] = "produto",
            ["qualidade"] = "produto",
            ["quantidade"] = "produto",
            ["temperatura"] = "produto",
            ["aparencia"] = "produto",
            ["preparo"] = "produto",
            ["atendimento"] = "loja",
            ["pedido_correto"] = "loja",
            ["embalagem"] = "loja",
            ["custo_beneficio"] = "loja",
            ["tempo_entrega"] = "entrega",
            ["condicao_entrega"] = "entrega"
        };

    public static bool IsValidAspect(string aspect) =>
        !string.IsNullOrWhiteSpace(aspect) && EntityMapping.ContainsKey(aspect);

    public static bool IsValidSentiment(string sentiment) =>
        !string.IsNullOrWhiteSpace(sentiment) && Sentiments.Contains(sentiment, StringComparer.OrdinalIgnoreCase);

    public static string ResolveEntity(string aspect) =>
        EntityMapping.TryGetValue(aspect, out var entity)
            ? entity
            : throw new ArgumentException($"Invalid aspect: {aspect}", nameof(aspect));
}
