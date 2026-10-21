int findLargest(int *values, int count)
{
    int largest = values[0];
    int idx = 1;
    while (idx < count) {
        if (values[idx] <= largest) {
            idx++;
            continue;
        }
        largest = values[idx];
        idx++;
    }
    return largest;
}
