static int is_prime(int candidate)
{
    for (int div = 2; div * div <= candidate; div++)
        if (candidate % div == 0)
            return 0;
    return 1;
}

int prime_counter(int limit)
{
    int total = 0;
    for (int candidate = 2; candidate < limit; candidate++)
        total += is_prime(candidate);
    return total;
}
