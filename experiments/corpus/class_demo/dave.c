/* Assignment 3 -- Dave (independent work: insertion sort, running median idea) */
void insertion_sort(int *a, int n) {
    for (int i = 1; i < n; i++) {
        int key = a[i];
        int j = i - 1;
        while (j >= 0 && a[j] > key) {
            a[j + 1] = a[j];
            j--;
        }
        a[j + 1] = key;
    }
}

int median_of_sorted(int *a, int n) {
    if (n == 0) {
        return 0;
    }
    if (n % 2 == 1) {
        return a[n / 2];
    }
    return (a[n / 2 - 1] + a[n / 2]) / 2;
}

int count_above(int *a, int n, int limit) {
    int count = 0;
    for (int i = 0; i < n; i++) {
        count += a[i] > limit;
    }
    return count;
}
