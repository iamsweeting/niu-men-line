from pythonforandroid.recipe import Recipe
from pythonforandroid.logger import shprint, info, info_main
from pythonforandroid.util import (
    current_directory, ensure_dir, rmdir,
)
from os.path import join, exists
from multiprocessing import cpu_count
import glob
import sh
import tarfile


class FreetypeRecipe(Recipe):
    """The freetype library it's special, because has cyclic dependencies with
    harfbuzz library, so freetype can be build with harfbuzz support, and
    harfbuzz can be build with freetype support. This complicates the build of
    both recipes because in order to get the full set we need to compile those
    recipes several times:
        - build freetype without harfbuzz
        - build harfbuzz with freetype
        - build freetype with harfbuzz support

    .. note::
        To build freetype with harfbuzz support you must add `harfbuzz` to your
        requirements, otherwise freetype will be build without harfbuzz

    .. seealso::
        https://sourceforge.net/projects/freetype/files/freetype2/2.5.3/

    本地覆盖：仅把下载源从 savannah.gnu.org 换成 GitHub mirror，并修正
    解压目录名（GitHub archive 顶层目录为 freetype-VER-2-14-1，与
    get_build_dir 的 freetype-2.14.1 不一致）。
    savannah.gnu.org 在 GitHub Actions 容器内偶发 502 Bad Gateway（站点级
    限流），导致 p4a 下载 freetype 源码失败；GitHub mirror 与 Actions 同
    基础设施，更稳定。其余逻辑与上游 pythonforandroid v2026.05.09 一致。
    """

    version = '2.14.1'

    @property
    def versioned_url(self):
        # freetype 的 GitHub tag 用连字符：VER-2-14-1
        dashed = self.version.replace('.', '-')
        return self.url.format(dashed=dashed)

    url = 'https://github.com/freetype/freetype/archive/refs/tags/VER-{dashed}.tar.gz'  # noqa
    built_libraries = {'libfreetype.so': 'objs/.libs'}

    def unpack(self, arch):
        info_main('Unpacking {} for {}'.format(self.name, arch))
        build_dir = self.get_build_container_dir(arch)
        filename = shprint(
            sh.basename, self.versioned_url
        ).stdout[:-1].decode('utf-8')
        extraction_filename = join(
            self.ctx.packages_path, self.name, filename
        )
        target = self.get_build_dir(arch)
        if exists(target):
            return
        rmdir(build_dir)
        ensure_dir(build_dir)
        with current_directory(build_dir):
            with tarfile.open(extraction_filename) as tf:
                tf.extractall()
            # GitHub archive 顶层目录为 freetype-VER-2-14-1，重命名为期望名
            for e in glob.glob(build_dir + '/freetype-*'):
                if e != target:
                    shprint(sh.mv, e, target)
                    break

    def get_recipe_env(self, arch=None, with_harfbuzz=False):
        env = super().get_recipe_env(arch)
        if with_harfbuzz:
            harfbuzz_build = self.get_recipe(
                'harfbuzz', self.ctx
            ).get_build_dir(arch.arch)
            freetype_install = join(self.get_build_dir(arch.arch), 'install')

            env['HARFBUZZ_CFLAGS'] = '-I{harfbuzz} -I{harfbuzz}/src'.format(
                harfbuzz=harfbuzz_build
            )
            env['HARFBUZZ_LIBS'] = (
                '-L{freetype}/lib -lfreetype '
                '-L{harfbuzz}/src/.libs -lharfbuzz'.format(
                    freetype=freetype_install, harfbuzz=harfbuzz_build
                )
            )

        # android's zlib support
        zlib_lib_path = arch.ndk_lib_dir_versioned
        zlib_includes = self.ctx.ndk.sysroot_include_dir

        def add_flag_if_not_added(flag, env_key):
            if flag not in env[env_key]:
                env[env_key] += flag

        add_flag_if_not_added(' -I' + zlib_includes, 'CFLAGS')
        add_flag_if_not_added(' -L' + zlib_lib_path, 'LDFLAGS')
        add_flag_if_not_added(' -lz', 'LDLIBS')

        return env

    def build_arch(self, arch, with_harfbuzz=False):
        env = self.get_recipe_env(arch, with_harfbuzz=with_harfbuzz)

        harfbuzz_in_recipes = 'harfbuzz' in self.ctx.recipe_build_order
        prefix_path = self.get_build_dir(arch.arch)
        if harfbuzz_in_recipes and not with_harfbuzz:
            prefix_path = join(prefix_path, 'install')

        config_args = {
            '--host={}'.format(arch.command_prefix),
            '--prefix={}'.format(prefix_path),
            '--without-bzip2',
            '--without-brotli',
            '--with-png=no',
        }
        if not harfbuzz_in_recipes:
            info('Build freetype (without harfbuzz)')
            config_args = config_args.union(
                {'--disable-static',
                 '--enable-shared',
                 '--with-harfbuzz=no',
                 '--with-zlib=yes',
                 }
            )
        elif not with_harfbuzz:
            info('Build freetype for First time (without harfbuzz)')
            config_args = config_args.union(
                {'--disable-shared', '--with-harfbuzz=no', '--with-zlib=no'}
            )
        else:
            info('Build freetype for Second time (with harfbuzz)')
            config_args = config_args.union(
                {'--disable-static',
                 '--enable-shared',
                 '--with-harfbuzz=yes',
                 '--with-zlib=yes',
                 }
            )
        info('Configure args are:\n\t-{}'.format('\n\t-'.join(config_args)))

        with current_directory(self.get_build_dir(arch.arch)):
            configure = sh.Command('./configure')
            shprint(configure, *config_args, _env=env)
            shprint(sh.make, '-j', str(cpu_count()), _env=env)

            if not with_harfbuzz and harfbuzz_in_recipes:
                info('Installing freetype (first time build without harfbuzz)')
                shprint(sh.make, 'install', _env=env)
                shprint(sh.make, 'distclean', _env=env)

    def install_libraries(self, arch):
        if not exists(list(self.get_libraries(arch))[0]):
            return
        self.install_libs(arch, *self.get_libraries(arch))


recipe = FreetypeRecipe()

