static void swap_ints(int *a, int *b)
{
    int t = *a;
    *a = *b;
    *b = t;
}

void sort_numbers(int *nums, int len)
{
    int swapped = 1;
    for (int pass = 0; swapped && pass < len - 1; pass++) {
        swapped = 0;
        for (int *p = nums; p < nums + len - 1 - pass; p++) {
            if (*p > *(p + 1)) {
                swap_ints(p, p + 1);
                swapped = 1;
            }
        }
    }
}
