/* Small in-process /proc/stat reader. No privileges, no process control. */
#define _GNU_SOURCE
#include <dirent.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct row {
    int pid;
    uint64_t ticks;
    uint64_t start;
    char state;
    char comm[64];
};

struct cached_fd { int pid, fd, seen; };
static struct cached_fd cache[8192];
static int generation;

static struct cached_fd *slot_for(int pid) {
    unsigned index = ((unsigned)pid * 2654435761u) & 8191u;
    for (unsigned n = 0; n < 8192; n++, index = (index + 1) & 8191u) {
        if (!cache[index].pid || cache[index].pid == pid) return &cache[index];
    }
    return NULL;
}

int procscan(struct row *rows, int capacity) {
    DIR *dir = opendir("/proc");
    if (!dir) return -1;
    struct dirent *ent;
    int count = 0;
    generation++;
    while ((ent = readdir(dir))) {
        char *endpid;
        long pid = strtol(ent->d_name, &endpid, 10);
        if (*endpid || pid <= 0 || count >= capacity) continue;
        char path[64], buf[1024];
        struct cached_fd *slot = slot_for((int)pid);
        if (!slot) continue;
        if (!slot->pid) {
            snprintf(path, sizeof(path), "/proc/%ld/stat", pid);
            slot->fd = open(path, O_RDONLY | O_CLOEXEC);
            if (slot->fd < 0) continue;
            slot->pid = (int)pid;
        }
        slot->seen = generation;
        ssize_t len = pread(slot->fd, buf, sizeof(buf) - 1, 0);
        if (len <= 0) continue;
        buf[len] = 0;
        char *left = strchr(buf, '('), *right = strrchr(buf, ')');
        if (!left || !right || right <= left) continue;
        struct row *r = &rows[count];
        r->pid = (int)pid;
        size_t clen = (size_t)(right - left - 1);
        if (clen >= sizeof(r->comm)) clen = sizeof(r->comm) - 1;
        memcpy(r->comm, left + 1, clen);
        r->comm[clen] = 0;
        char *p = right + 2;
        int field = 0;
        uint64_t utime = 0, stime = 0, start = 0;
        while (*p && field <= 19) {
            while (*p == ' ') p++;
            char *next = p;
            while (*next && *next != ' ') next++;
            if (field == 0) r->state = *p;
            else if (field == 11) utime = strtoull(p, NULL, 10);
            else if (field == 12) stime = strtoull(p, NULL, 10);
            else if (field == 19) start = strtoull(p, NULL, 10);
            p = next;
            field++;
        }
        if (field <= 19) continue;
        r->ticks = utime + stime;
        r->start = start;
        count++;
    }
    closedir(dir);
    for (int i = 0; i < 8192; i++) {
        if (cache[i].pid && cache[i].seen != generation) {
            close(cache[i].fd);
            cache[i].pid = 0;
        }
    }
    return count;
}
