/* Assignment 3 -- Erin (Alice's code, loops rewritten and conditions flipped) */
void order_values(int *v, int len) {
    int pass = 0;
    while (pass < len - 1) {
        int k = 0;
        while (k < len - 1 - pass) {
            if (!(v[k] <= v[k + 1])) {
                int held = v[k];
                v[k] = v[k + 1];
                v[k + 1] = held;
            }
            k++;
        }
        pass++;
    }
}

int maximum(int *v, int len) {
    int m = v[0];
    int k = 1;
    while (k < len) {
        if (v[k] <= m) {
            k++;
            continue;
        }
        m = v[k];
        k++;
    }
    return m;
}
