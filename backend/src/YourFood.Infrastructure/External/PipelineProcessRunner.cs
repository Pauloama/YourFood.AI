using System.Diagnostics;
using System.Text;
using Microsoft.Extensions.Options;
using YourFood.Application.Interfaces;
using YourFood.Domain.Enums;

namespace YourFood.Infrastructure.External;

public class PipelineProcessRunner : IPipelineProcessRunner
{
    private readonly AbsaServiceSettings _settings;

    public PipelineProcessRunner(IOptions<AbsaServiceSettings> options)
    {
        _settings = options.Value;
    }

    public string BuildCommandPreview(PipelineStepType step, string? datasetFileName, int seed)
    {
        var inputName = ResolveInputFile(datasetFileName);
        return step switch
        {
            PipelineStepType.ValidateDataset => $"{_settings.PythonExecutable} scripts/validate_dataset.py --input data/raw/{inputName} --output reports/validation",
            PipelineStepType.PrepareDataset => $"{_settings.PythonExecutable} scripts/prepare_dataset.py --input data/raw/{inputName} --output data/processed",
            PipelineStepType.SplitDataset => $"{_settings.PythonExecutable} scripts/split_dataset.py --input data/processed/reviews.jsonl --output data/splits --seed {seed}",
            PipelineStepType.TrainAspectDetector => $"{_settings.PythonExecutable} scripts/train_aspect_detector.py --config configs/train_aspects.yaml",
            PipelineStepType.TrainSentimentClassifier => $"{_settings.PythonExecutable} scripts/train_sentiment_classifier.py --config configs/train_sentiment.yaml",
            PipelineStepType.EvaluatePipeline => $"{_settings.PythonExecutable} scripts/evaluate_pipeline.py --input data/splits/test.jsonl --output reports/final",
            PipelineStepType.ExportModels => $"{_settings.PythonExecutable} scripts/export_models.py --source artifacts --destination artifacts/exported",
            PipelineStepType.FullDataPreparation => $"validate -> prepare -> split (seed={seed}) on data/raw/{inputName}",
            _ => "export dataset"
        };
    }

    public string SaveDatasetFile(string fileName, string content)
    {
        var rootDir = ResolvePipelineRoot();
        var rawDir = Path.Combine(rootDir, "data", "raw");
        Directory.CreateDirectory(rawDir);
        var fullPath = Path.Combine(rawDir, Path.GetFileName(fileName));
        File.WriteAllText(fullPath, content, new UTF8Encoding(false));
        return fullPath;
    }

    public async Task<(int ExitCode, string OutputLog, string ErrorLog, string? ReportJson)> ExecuteStepAsync(PipelineStepType step, string? datasetFileName, int seed, CancellationToken ct = default)
    {
        var rootDir = ResolvePipelineRoot();
        if (!Directory.Exists(rootDir))
            return (-1, string.Empty, $"Pipeline directory not found at '{rootDir}'.", null);

        if (step == PipelineStepType.FullDataPreparation)
        {
            var steps = new[] { PipelineStepType.ValidateDataset, PipelineStepType.PrepareDataset, PipelineStepType.SplitDataset };
            var combinedOut = new StringBuilder();
            var combinedErr = new StringBuilder();
            string? lastReport = null;

            foreach (var subStep in steps)
            {
                var (code, stdout, stderr, report) = await ExecuteSingleScriptAsync(rootDir, subStep, datasetFileName, seed, ct);
                combinedOut.AppendLine($"=== {subStep} (exit {code}) ===");
                combinedOut.AppendLine(stdout);
                if (!string.IsNullOrWhiteSpace(stderr))
                    combinedErr.AppendLine(stderr);
                if (report is not null)
                    lastReport = report;
                if (code != 0)
                    return (code, combinedOut.ToString(), combinedErr.ToString(), lastReport);
            }

            return (0, combinedOut.ToString(), combinedErr.ToString(), lastReport);
        }

        return await ExecuteSingleScriptAsync(rootDir, step, datasetFileName, seed, ct);
    }

    private async Task<(int ExitCode, string OutputLog, string ErrorLog, string? ReportJson)> ExecuteSingleScriptAsync(
        string rootDir,
        PipelineStepType step,
        string? datasetFileName,
        int seed,
        CancellationToken ct)
    {
        var inputName = ResolveInputFile(datasetFileName);
        var rawCandidate = Path.Combine(rootDir, "data", "raw", inputName);
        if (step is PipelineStepType.ValidateDataset or PipelineStepType.PrepareDataset && !File.Exists(rawCandidate))
        {
            inputName = "sample_reviews.jsonl";
        }

        var args = step switch
        {
            PipelineStepType.ValidateDataset => $"scripts/validate_dataset.py --input data/raw/{inputName} --output reports/validation",
            PipelineStepType.PrepareDataset => $"scripts/prepare_dataset.py --input data/raw/{inputName} --output data/processed",
            PipelineStepType.SplitDataset => $"scripts/split_dataset.py --input data/processed/reviews.jsonl --output data/splits --seed {seed}",
            PipelineStepType.TrainAspectDetector => "scripts/train_aspect_detector.py --config configs/train_aspects.yaml",
            PipelineStepType.TrainSentimentClassifier => "scripts/train_sentiment_classifier.py --config configs/train_sentiment.yaml",
            PipelineStepType.EvaluatePipeline => "scripts/evaluate_pipeline.py --input data/splits/test.jsonl --output reports/final",
            PipelineStepType.ExportModels => "scripts/export_models.py --source artifacts --destination artifacts/exported",
            _ => string.Empty
        };

        var startInfo = new ProcessStartInfo
        {
            FileName = _settings.PythonExecutable,
            Arguments = args,
            WorkingDirectory = rootDir,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };

        try
        {
            using var process = new Process { StartInfo = startInfo };
            process.Start();

            var stdoutTask = process.StandardOutput.ReadToEndAsync(ct);
            var stderrTask = process.StandardError.ReadToEndAsync(ct);
            await process.WaitForExitAsync(ct);

            var stdout = await stdoutTask;
            var stderr = await stderrTask;
            var reportJson = TryReadReportJson(rootDir, step);

            return (process.ExitCode, stdout, stderr, reportJson);
        }
        catch (Exception ex)
        {
            return (-1, string.Empty, ex.Message, null);
        }
    }

    private static string? TryReadReportJson(string rootDir, PipelineStepType step)
    {
        var path = step switch
        {
            PipelineStepType.ValidateDataset => Path.Combine(rootDir, "reports", "validation", "validation_report.json"),
            PipelineStepType.PrepareDataset => Path.Combine(rootDir, "data", "processed", "preparation_manifest.json"),
            PipelineStepType.SplitDataset => Path.Combine(rootDir, "data", "splits", "split_manifest.json"),
            PipelineStepType.EvaluatePipeline => Path.Combine(rootDir, "reports", "final", "integrated_pipeline_evaluation.json"),
            _ => null
        };

        if (path is null || !File.Exists(path))
            return null;

        return File.ReadAllText(path, Encoding.UTF8);
    }

    private string ResolvePipelineRoot() =>
        Path.GetFullPath(_settings.PipelineRootPath);

    private static string ResolveInputFile(string? datasetFileName) =>
        string.IsNullOrWhiteSpace(datasetFileName) ? "delivery_reviews.jsonl" : Path.GetFileName(datasetFileName);
}
