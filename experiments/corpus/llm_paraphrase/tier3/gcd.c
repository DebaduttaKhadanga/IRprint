int highest_common_factor(int first, int second)
{
    int a = first < 0 ? -first : first;
    int b = second < 0 ? -second : second;
    while (b) {
        int q = a / b;
        int r = a - q * b;
        a = b;
        b = r;
    }
    return a;
}
