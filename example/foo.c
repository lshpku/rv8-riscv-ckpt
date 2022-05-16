#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define N 12
#define E 1e-4
#define S 16384
#define B 64

#define EQUAL(a, b) ((a) - (b) < E && (b) - (a) < E)

static float det[1 << N];
static float cof[N][N];

static void dp(int i, int j, int x, int n, int m)
{
    if (j == n) {
        int sign = 1;
        float d = 0;
        for (int k = 0; k < m; k++) {
            if (x & (1 << k)) {
                d += sign * cof[m - n][k] * det[x ^ (1 << k)];
                sign = -sign;
            }
        }
        det[x] = d;
        return;
    }
    if (i + n - j < m)
        dp(i + 1, j, x, n, m);
    dp(i + 1, j + 1, x | (1 << i), n, m);
}

static void adjoint(float A[N][N], float adj[N][N])
{
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            for (int x = 0, ci = 0; x < N; x++) {
                if (x == i)
                    continue;
                for (int y = 0, cj = 0; y < N; y++) {
                    if (y == j)
                        continue;
                    cof[ci][cj++] = A[x][y];
                }
                ci++;
            }
            for (int n = 1; n < N; n++)
                dp(0, 0, 0, n, N - 1);
            int sign = ((i + j) % 2 == 0) ? 1 : -1;
            adj[j][i] = sign * det[(1 << (N - 1)) - 1];
        }
    }
}

static int inverse(float A[N][N], float inv[N][N])
{
    det[0] = 1;
    memcpy((void *)cof, A, N * N * sizeof(float));
    for (int n = 1; n <= N; n++)
        dp(0, 0, 0, n, N);
    float d = det[(1 << N) - 1];
    if (EQUAL(d, 0)) {
        return -1;
    }
    float adj[N][N];
    adjoint(A, adj);
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            inv[i][j] = adj[i][j] / d;
    return 0;
}

struct node {
    struct node *prev;
    struct node *succ;
    char *str;
};
typedef struct node node_t;

static void swapl(node_t *i, node_t *j)
{
    if (i != j) {
        char *tmp = i->str;
        i->str = j->str;
        j->str = tmp;
    }
}

static void qsortl(node_t *head, node_t *tail)
{
    if (head == tail || head->succ == tail)
        return;
    node_t *i = head;
    for (node_t *j = head->succ; j != tail; j = j->succ) {
        if (strcmp(j->str, tail->str) < 0) {
            i = i->succ;
            swapl(i, j);
        }
    }
    swapl(i->succ, tail);
    qsortl(head, i);
    qsortl(i->succ, tail);
}

int main()
{
    struct timespec start, stop;
    clock_gettime(CLOCK_REALTIME, &start);

    printf("Task 1: Memory allocation\n");
    char buf[B];
    node_t head = {};
    node_t *tail = &head;
    for (int i = 0; i < S; i++) {
        node_t *cur = malloc(sizeof(node_t));
        int j;
        for (j = 0; j < B - 1; j++) {
            buf[j] = rand() & 7;
            if (!buf[j])
                break;
        }
        if (j == B - 1)
            buf[j] = 0;
        cur->str = strdup(buf);
        cur->prev = tail;
        cur->succ = NULL;
        tail->succ = cur;
        tail = cur;
    }
    printf("success\n");

    printf("Task 2: List sorting\n");
    qsortl(&head, tail);
    for (tail = head.succ; tail->succ; tail = tail->succ) {
        if (strcmp(tail->str, tail->succ->str) > 0) {
            printf("failed: unordered list\n");
            goto task2_done;
        }
    }
    printf("success\n");
task2_done:

    printf("Task 3: Matrix inversion\n");
    float A[N][N];
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            A[i][j] = (float)rand() / RAND_MAX;
    float inv[N][N];
    inverse(A, inv);
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            float d = 0;
            for (int k = 0; k < N; k++)
                d += A[i][k] * inv[k][j];
            if (i == j && EQUAL(d, 1))
                continue;
            if (i != j && EQUAL(d, 0))
                continue;
            printf("failed: not an identity matrix\n");
            goto task3_done;
        }
    }
    printf("success\n");
task3_done:

    clock_gettime(CLOCK_REALTIME, &stop);
    time_t sec;
    long nsec;
    if (stop.tv_nsec < start.tv_nsec) {
        sec = stop.tv_sec - start.tv_sec - 1;
        nsec = stop.tv_nsec + 1000000000L - start.tv_nsec;
    } else {
        sec = stop.tv_sec - start.tv_sec;
        nsec = stop.tv_nsec - start.tv_nsec;
    }
    printf("Running time: %ld.%09lds\n", sec, nsec);
    return 0;
}
