#include <stdio.h>

int globalCounter = 0;  // initialized global variable

int sumArray(int* arr, int n) {
    int sum = 0;  // initialized local variable
    for (int i = 0; i < n; i++) {  // fixed off-by-one error
        if (i >= 0 && i < n) {
            sum += arr[i];
        }
    }
    return sum;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};

    // Optimized nested loops
    int result = 0;
    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5; j++) {
            if (i >= 0 && i < 5 && j >= 0 && j < 5) {
                result += data[i] * data[j];
            }
        }
    }

    printf("Sum:     %d\n", sumArray(data, 5));
    printf("Result:  %d\n", result);
    printf("Counter: %d\n", globalCounter);  // initialized global

    // Safe division
    int divisor = 1;
    printf("Ratio: %d\n", result / divisor);

    return 0;
}