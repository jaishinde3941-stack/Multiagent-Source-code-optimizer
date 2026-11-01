// Category: Array/Buffer Errors (Success Case)
// Expected Result: Negative index should be avoided

#include <iostream>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int index = 0;  // SUCCESS: Changed to valid non-negative index
    
    if (index >= 0 && index < 5) {
        int value = arr[index];
        std::cout << "Value: " << value << std::endl;
    }
    
    return 0;
}
