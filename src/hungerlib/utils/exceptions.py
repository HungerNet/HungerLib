# HungerLib exceptions
class HungerLibError(Exception): pass

class InvalidLevelError(HungerLibError): pass
class InvalidModeError(HungerLibError): pass

# HungerBridge exceptions
class HungerBridgeError(Exception): pass


# Method exceptions
class InvalidMethodError(Exception): pass

class RenamedMethodError(InvalidMethodError): pass
class RemovedMethodError(InvalidMethodError): pass

# Validation exceptions
class ValidationError(Exception):
    def __init__(self, report, errors=None, warnings=None, fallbacks=None, recommended=None):
        super().__init__(report)
        self.report = report
        self.errors = errors or []
        self.warnings = warnings or []
        self.fallbacks = fallbacks or []
        self.recommended = recommended or []

class FatalError(ValidationError): pass
class TypeMismatchError(ValidationError): pass
class FallbackError(ValidationError): pass
class RecommendedError(ValidationError): pass
