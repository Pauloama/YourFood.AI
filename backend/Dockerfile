FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY src/YourFood.Domain/YourFood.Domain.csproj src/YourFood.Domain/
COPY src/YourFood.Application/YourFood.Application.csproj src/YourFood.Application/
COPY src/YourFood.Infrastructure/YourFood.Infrastructure.csproj src/YourFood.Infrastructure/
COPY src/YourFood.Api/YourFood.Api.csproj src/YourFood.Api/
RUN dotnet restore src/YourFood.Api/YourFood.Api.csproj

COPY src/ src/
RUN dotnet publish src/YourFood.Api/YourFood.Api.csproj -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl python3 python3-venv python3-yaml python3-numpy python3-sklearn && rm -rf /var/lib/apt/lists/*
RUN groupadd --system appgroup && useradd --system --gid appgroup --create-home appuser

COPY --from=build /app/publish .
RUN chown -R appuser:appgroup /app

USER appuser
ENV ASPNETCORE_URLS=http://+:5000
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

ENTRYPOINT ["dotnet", "YourFood.Api.dll"]
