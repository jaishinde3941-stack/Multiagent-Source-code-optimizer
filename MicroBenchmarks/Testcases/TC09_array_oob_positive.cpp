// Category: Array/Buffer Errors
// Error: Array index out of bounds (positive)

#include <iostream>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    
    int value = arr[10];  // ERROR: Index 10 is out of bounds (valid: 0-4)
    std::cout << "Value: " << value << std::endl;
    
    return 0;
}
