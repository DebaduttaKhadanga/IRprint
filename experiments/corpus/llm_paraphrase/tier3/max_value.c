static int bigger(int x, int y) { return x > y ? x : y; }

int findLargest(int *values, int count)
{
    int *end = values + count;
    int largest = *values;
    for (int *p = values + 1; p < end; ++p)
        largest = bigger(*p, largest);
    return largest;
}
