namespace YourFood.Domain.Exceptions;

public class DomainException : Exception
{
    public string Code { get; }
    public int StatusCode { get; }

    public DomainException(string message, string code = "DOMAIN_ERROR", int statusCode = 400)
        : base(message)
    {
        Code = code;
        StatusCode = statusCode;
    }
}

public class NotFoundException : DomainException
{
    public NotFoundException(string resource, object identifier)
        : base($"{resource} with identifier '{identifier}' was not found.", "RESOURCE_NOT_FOUND", 404)
    {
    }
}

public class ForbiddenException : DomainException
{
    public ForbiddenException(string message = "Access denied.")
        : base(message, "FORBIDDEN", 403)
    {
    }
}

public class ConflictException : DomainException
{
    public ConflictException(string message)
        : base(message, "CONFLICT", 409)
    {
    }
}
