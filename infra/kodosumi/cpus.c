// Report UPLIFT_CPUS (default 2) as the CPU count. Hosted containers expose every host core (48+) while
// capping threads at ~1000; Ray, gRPC and Python size their thread pools from the visible core count.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
#include <unistd.h>

static long cpus(void) {
    const char *v = getenv("UPLIFT_CPUS");
    long n = v ? atol(v) : 2;
    return n > 0 ? n : 2;
}

int get_nprocs(void) { return (int)cpus(); }
int get_nprocs_conf(void) { return (int)cpus(); }

long sysconf(int name) {
    static long (*real)(int) = 0;
    if (!real) real = (long (*)(int))dlsym(RTLD_NEXT, "sysconf");
    if (name == _SC_NPROCESSORS_ONLN || name == _SC_NPROCESSORS_CONF) return cpus();
    return real(name);
}
