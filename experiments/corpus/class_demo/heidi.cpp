// Assignment 3 -- Heidi (independent C++ solution: shell sort + range)
#include <vector>

void shell_sort(std::vector<int> &v) {
    for (size_t gap = v.size() / 2; gap > 0; gap /= 2) {
        for (size_t i = gap; i < v.size(); i++) {
            int value = v[i];
            size_t j = i;
            while (j >= gap && v[j - gap] > value) {
                v[j] = v[j - gap];
                j -= gap;
            }
            v[j] = value;
        }
    }
}

int score_range(const std::vector<int> &v) {
    int lo = v[0], hi = v[0];
    for (int x : v) {
        if (x < lo) lo = x;
        if (x > hi) hi = x;
    }
    return hi - lo;
}
