// Finds the maximum in a list of numbers
int findLargest(int *values, int count)
{
    int largest = values[0];
    for (int idx = 1; idx < count; idx++)
    {
        if (values[idx] > largest)
            largest = values[idx];
    }
    return largest;
}
