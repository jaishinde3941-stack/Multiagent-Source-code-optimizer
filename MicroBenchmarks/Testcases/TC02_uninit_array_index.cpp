// Category: Uninitialized Variables
// Error: Using uninitialized variable as array index

#include <iostream>

int main() {
    int arr[10] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    int index;
    
    std::cout << "Value: " << arr[index] << std::endl;  // ERROR: index is uninitialized
    
    return 0;
}
