from dataclasses import fields
from .utils.exceptions import ValidationError, FatalError, TypeMismatchError, FallbackError, RecommendedError


class Validator:
    def __init__(
        self,

        msg_missing_required='{field}: missing required key',
        msg_missing_recommended='{field}: key missing, using fallback {fallback}',
        msg_fallback_required='{field}: must not use fallback (got {value})',
        msg_fallback_recommended='{field}: using fallback {value}',
        msg_type_mismatch='{schema}.{field}: expected {expected}, got {actual} ({value!r})',
    ):
        # collected results
        self.errors = []
        self.warnings = []
        self.fallbacks = []
        self.recommended = []

        # message templates
        self.msg_missing_required = msg_missing_required
        self.msg_missing_recommended = msg_missing_recommended
        self.msg_fallback_required = msg_fallback_required
        self.msg_fallback_recommended = msg_fallback_recommended
        self.msg_type_mismatch = msg_type_mismatch

    # type checking
    def validate_key_types(self, obj, schema):
        for f in fields(schema):
            if f.name.startswith('__'):
                continue

            expected = f.type
            value = getattr(obj, f.name, None)

            if value is None:
                continue

            try:
                if not isinstance(value, expected):
                    msg = self.msg_type_mismatch.format(
                        schema=schema.__name__,
                        field=f.name,
                        expected=getattr(expected, '__name__', str(expected)),
                        actual=type(value).__name__,
                        value=value,
                    )
                    self.errors.append(msg)
            except TypeError:
                pass

    # rule lookup
    def _rule(self, obj, name):
        rules = getattr(obj.__class__, 'rules', None)
        if rules is None:
            return 'optional'
        return getattr(rules, name, 'optional')

    # field checking
    def check_field(self, obj, name):
        raw = getattr(obj, 'raw', None)
        fb = getattr(obj, 'fallbacks', None)
        if raw is None or fb is None:
            return

        val = getattr(obj, name)
        raw_val = raw.__dict__.get(name, None)
        fb_val = getattr(fb, name)
        level = self._rule(obj, name)

        # missing yaml key
        if raw_val is None:
            if level == 'required':
                self.errors.append(self.msg_missing_required.format(field=name))
            elif level == 'recommended':
                self.recommended.append(self.msg_missing_recommended.format(field=name, fallback=fb_val))
            return

        # fallback usage
        if fb_val is not None and val == fb_val:
            if level == 'required':
                self.errors.append(self.msg_fallback_required.format(field=name, value=val))
            elif level == 'recommended':
                self.fallbacks.append(self.msg_fallback_recommended.format(field=name, value=val))

    # subclass hook
    def validate_schema(self, obj):
        pass

    # run and throw highest priority error
    def run(self, *configs):
        for cfg in configs:
            self.validate_schema(cfg)

        report = self.format_report()

        # required errors
        if self.errors:
            raise FatalError(report, self.errors, self.warnings, self.fallbacks, self.recommended)

        # type mismatch
        if any('expected' in e for e in self.errors):
            raise TypeMismatchError(report, self.errors, self.warnings, self.fallbacks, self.recommended)

        # fallback used
        if self.fallbacks:
            raise FallbackError(report, self.errors, self.warnings, self.fallbacks, self.recommended)

        # recommended missing
        if self.recommended:
            raise RecommendedError(report, self.errors, self.warnings, self.fallbacks, self.recommended)

        return report

    # reporting
    def format_report(self):
        out = []

        if self.errors:
            out.append('errors:')
            for e in self.errors:
                out.append(f' - {e}')

        if self.recommended:
            out.append('recommended:')
            for r in self.recommended:
                out.append(f' - {r}')

        if self.fallbacks:
            out.append('fallbacks:')
            for f in self.fallbacks:
                out.append(f' - {f}')

        if self.warnings:
            out.append('warnings:')
            for w in self.warnings:
                out.append(f' - {w}')

        if not out:
            return 'all configs valid'

        return '\n'.join(out)
