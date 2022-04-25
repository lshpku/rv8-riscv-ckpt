#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <time.h>

int main(int argc, char **argv)
{
    struct timespec start, stop;

    if (clock_gettime(CLOCK_REALTIME, &start) == -1) {
        return -1;
    }

    printf("Hello, world!\n");

    if (clock_gettime(CLOCK_REALTIME, &stop) == -1) {
        return -1;
    }

    time_t sec;
    long nsec;
    if (stop.tv_nsec < start.tv_nsec) {
        sec = stop.tv_sec - start.tv_sec - 1;
        nsec = stop.tv_nsec + 1000000000L - start.tv_nsec;
    } else {
        sec = stop.tv_sec - start.tv_sec;
        nsec = stop.tv_nsec - start.tv_nsec;
    }
    printf("Running time: %ld.%09lds!\n", sec, nsec);
    return 0;
}
