// Euclid: highest common factor of two integers
int highest_common_factor(int first, int second)
{
    while (second != 0)
    {
        int remainder = first % second;
        first = second;
        second = remainder;
    }
    return first;
}
