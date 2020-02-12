from os.path import dirname
from django.conf import settings
from pipeline.compilers import sass


class AutoprefixerMixin:
    def compile_file(self, infile, outfile, **kwargs):
        super().compile_file(infile, outfile, **kwargs)
        command = (
            settings.PIPELINE_AUTOPREFIXER_BINARY,
            outfile,
            '--map=false',
            '--use=autoprefixer',
            '-o' + outfile
        )
        return self.execute_command(command, cwd=dirname(outfile))


class AutoprefixerSASSCompiler(AutoprefixerMixin, sass.SASSCompiler):
    pass
