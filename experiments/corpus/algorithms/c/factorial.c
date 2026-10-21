/* Iterative factorial. */
long factorial(int n) {
    long result = 1;
    for (int i = 2; i <= n; i++) {
        result = result * i;
    }
    return result;
}
