namespace YourFood.Domain.Enums;

public enum UserRole
{
    Customer = 1,
    StoreOwner = 2,
    Admin = 3
}

public enum OrderStatus
{
    PendingPayment = 1,
    Confirmed = 2,
    Preparing = 3,
    ReadyForPickup = 4,
    OutForDelivery = 5,
    Delivered = 6,
    Cancelled = 7
}

public enum LedgerEntryType
{
    OrderCharge = 1,
    OrderRefund = 2,
    MerchantSettlement = 3
}

public enum PipelineStepType
{
    ExportDataset = 1,
    ValidateDataset = 2,
    PrepareDataset = 3,
    SplitDataset = 4,
    TrainAspectDetector = 5,
    TrainSentimentClassifier = 6,
    EvaluatePipeline = 7,
    ExportModels = 8,
    FullDataPreparation = 9
}

public enum PipelineJobStatus
{
    Queued = 1,
    Running = 2,
    Succeeded = 3,
    Failed = 4
}
