#include <stdio.h>

int globalCounter = 0;  // initialized global variable

int sumArray(int* arr, int n) {
    int sum = 0;  // initialized local variable
    for (int i = 0; i < n; i++) {  // corrected loop condition
        sum += arr[i];
    }
    return sum;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};

    // Optimized nested loops
    int result = 0;
    for (int i = 0; i < 5; i++) {
        result += data[i] * (data[0] + data[1] + data[2] + data[3] + data[4]);
    }

    printf("Sum:     %d\n", sumArray(data, 5));
    printf("Result:  %d\n", result);
    printf("Counter: %d\n", globalCounter);  // initialized global

    // Safe division by zero
    int divisor = 0;
    if (divisor != 0) {
        printf("Ratio: %d\n", result / divisor);
    } else {
        printf("Division by zero error\n");
    }

    return 0;
}