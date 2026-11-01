// Category: Array/Buffer Errors (Success Case)
// Expected Result: Loop range should stay within array bounds

#include <iostream>

int main() {
    int arr[5];
    
    for (int i = 0; i < 5; i++) {  // SUCCESS: i < 5 (indices 0, 1, 2, 3, 4)
        arr[i] = i * 2;
    }
    
    return 0;
}
