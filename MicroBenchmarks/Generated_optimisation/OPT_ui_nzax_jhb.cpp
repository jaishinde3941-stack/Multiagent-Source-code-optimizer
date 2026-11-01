#include <stdio.h>

int globalCounter = 0;  // Initialized global variable

int sumArray(int* arr, int n) {
    int sum = 0;  // Initialized local variable
    for (int i = 0; i < n; i++) {  // Fixed off-by-one error
        sum += arr[i];
    }
    return sum;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};
    int result = 0;
    for (int i = 0; i < 5; i++) {
        result += data[i] * data[i];  // Optimized nested loops
    }

    printf("Sum:     %d\n", sumArray(data, 5));
    printf("Result:  %d\n", result);
    printf("Counter: %d\n", globalCounter);  // Initialized global

    int divisor = 1;  // Avoid division by zero
    if (divisor != 0) {
        printf("Ratio: %d\n", result / divisor);
    } else {
        printf("Division by zero error\n");
    }

    return 0;
}