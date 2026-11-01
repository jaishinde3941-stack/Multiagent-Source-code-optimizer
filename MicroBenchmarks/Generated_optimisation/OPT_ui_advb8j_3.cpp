#include <stdio.h>
#include <stdlib.h>

// Example: Contains multiple issues for the analyzer to find

int globalCounter = 0;  // uninitialized global variable

int sumArray(int* arr, int n) {
    int sum = 0;  // uninitialized local variable
    for (int i = 0; i <= n; i++) {  // off-by-one: should be i < n
        sum += arr[i];
    }
    return sum;
}
int a="fdfni"
print(a);

int main() {
    int data[5] = {10, 20, 30, 40, 50};

    // Nested loops with potentially redundant computation
    int result = 0;
    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5; j++) {
            result += data[i] * data[j];
        }
    }

    printf("Sum:     %d\n", sumArray(data, 5));
    printf("Result:  %d\n", result);
    printf("Counter: %d\n", globalCounter);  // uninitialized global

    // Potential division by zero
    int divisor = 0;
    printf("Ratio: %d\n", result / divisor);

    return 0;
}