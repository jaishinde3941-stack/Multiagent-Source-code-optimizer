// Category: Array/Buffer Errors
// Error: Negative array index

#include <iostream>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int index = -1;
    
    int value = arr[index];  // ERROR: Negative index
    std::cout << "Value: " << value << std::endl;
    
    return 0;
}
