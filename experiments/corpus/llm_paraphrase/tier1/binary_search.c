// Look up key inside sorted data using bisection
int bisect_find(int *data, int size, int key)
{
    int low = 0, high = size - 1;
    while (low <= high)
    {
        int middle = low + (high - low) / 2;
        if (data[middle] == key)
            return middle;
        else if (data[middle] < key)
            low = middle + 1;
        else
            high = middle - 1;
    }
    return -1;
}
