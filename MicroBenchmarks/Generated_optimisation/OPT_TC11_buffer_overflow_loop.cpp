// Category: Array/Buffer Errors
// Error: Buffer overflow in loop

#include <iostream>

int main() {
    int arr[3];
    
    for (int i = 0; i < 3; i++) {  // ERROR: Off-by-one, writes to arr[5]
        arr[i] = i * 2;
    }
    
    return 0;
}
